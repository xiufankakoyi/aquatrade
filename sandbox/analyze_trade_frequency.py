"""
分析交易记录频繁的原因
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from collections import defaultdict, Counter
from numba import njit

from data_cache import get_cache, PreloadedData


@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    multiplier = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema


@njit
def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return dif, dea, histogram


@njit
def detect_signal(bars: np.ndarray) -> np.ndarray:
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3):
                if b3 > -0.005:
                    signals[i] = True
    
    return signals


def analyze_trades(data: PreloadedData, start_date: str, end_date: str,
                   position_per_stock: float = 0.02, max_total_position: float = 0.80,
                   take_profit_pct: float = 0.03, max_hold_days: int = 10,
                   trailing_pct: float = 0.02):
    """
    分析交易记录
    """
    
    all_trades = []
    signal_count_by_stock = Counter()
    signal_count_by_date = Counter()
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        stock_signal_count = 0
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sell_date = buy_date
                peak_price = buy_price
                triggered_trailing = False
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        triggered_trailing = True
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= trailing_pct:
                            sell_price = close[check_idx]
                            sell_date = str(dates[check_idx])
                            sold = True
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret,
                    'hold_days': (pd.to_datetime(sell_date) - pd.to_datetime(buy_date)).days
                })
                
                stock_signal_count += 1
                signal_count_by_date[buy_date] += 1
        
        signal_count_by_stock[stock_code] = stock_signal_count
    
    print("=" * 70)
    print("交易记录分析")
    print("=" * 70)
    
    print(f"\n生成的信号总数: {len(all_trades)}")
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    capital = 100000.0
    holdings = {}
    equity_curve = []
    executed_trades = []
    rejected_by_position = 0
    rejected_by_duplicate = 0
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                executed_trades.append({
                    'stock_code': stock_code,
                    'buy_date': h['buy_date'],
                    'sell_date': date,
                    'return': h['return'],
                    'position_value': h['position_value']
                })
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    rejected_by_duplicate += 1
                    continue
                
                if current_position_pct + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                        'buy_date': t['buy_date']
                    }
                    current_position_pct += position_per_stock
                else:
                    rejected_by_position += 1
        
        equity_curve.append({'date': date, 'equity': capital})
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
        executed_trades.append({
            'stock_code': stock_code,
            'buy_date': h['buy_date'],
            'sell_date': h['sell_date'],
            'return': h['return'],
            'position_value': h['position_value']
        })
    
    print(f"\n实际执行的交易数: {len(executed_trades)}")
    print(f"因仓位上限拒绝: {rejected_by_position}")
    print(f"因重复持仓拒绝: {rejected_by_duplicate}")
    
    print(f"\n涉及股票数: {len(signal_count_by_stock)}")
    print(f"平均每只股票交易次数: {len(all_trades) / len(signal_count_by_stock):.2f}")
    
    print("\n每只股票交易次数分布:")
    trade_counts = list(signal_count_by_stock.values())
    print(f"  最小: {min(trade_counts)}")
    print(f"  最大: {max(trade_counts)}")
    print(f"  中位数: {np.median(trade_counts):.0f}")
    
    print("\n交易次数最多的前10只股票:")
    for stock, count in signal_count_by_stock.most_common(10):
        print(f"  {stock}: {count}次")
    
    print("\n每天买入信号数量分布:")
    daily_signals = list(signal_count_by_date.values())
    print(f"  最小: {min(daily_signals)}")
    print(f"  最大: {max(daily_signals)}")
    print(f"  平均: {np.mean(daily_signals):.2f}")
    print(f"  中位数: {np.median(daily_signals):.0f}")
    
    print("\n信号最多的前10天:")
    for date, count in signal_count_by_date.most_common(10):
        print(f"  {date}: {count}个信号")
    
    df = pd.DataFrame(all_trades)
    df['buy_date'] = pd.to_datetime(df['buy_date'])
    df['sell_date'] = pd.to_datetime(df['sell_date'])
    
    print("\n持仓天数分布:")
    print(f"  最小: {df['hold_days'].min()}")
    print(f"  最大: {df['hold_days'].max()}")
    print(f"  平均: {df['hold_days'].mean():.2f}")
    print(f"  中位数: {df['hold_days'].median():.0f}")
    
    print("\n持仓天数统计:")
    for days in sorted(df['hold_days'].unique()):
        count = len(df[df['hold_days'] == days])
        print(f"  {days}天: {count}次 ({count/len(df)*100:.1f}%)")
    
    print("\n检查同一股票重复买入问题:")
    df_sorted = df.sort_values(['stock_code', 'buy_date'])
    
    overlap_count = 0
    overlap_examples = []
    
    for stock_code in df_sorted['stock_code'].unique():
        stock_trades = df_sorted[df_sorted['stock_code'] == stock_code]
        if len(stock_trades) <= 1:
            continue
        
        trades_list = stock_trades.to_dict('records')
        for i in range(len(trades_list) - 1):
            curr = trades_list[i]
            next_trade = trades_list[i + 1]
            
            if next_trade['buy_date'] <= curr['sell_date']:
                overlap_count += 1
                if len(overlap_examples) < 5:
                    overlap_examples.append({
                        'stock': stock_code,
                        'curr_buy': str(curr['buy_date'].date()),
                        'curr_sell': str(curr['sell_date'].date()),
                        'next_buy': str(next_trade['buy_date'].date())
                    })
    
    print(f"  发现 {overlap_count} 次重叠买入（新买入时前一笔还未卖出）")
    
    if overlap_examples:
        print("\n重叠买入示例:")
        for ex in overlap_examples:
            print(f"  {ex['stock']}: 当前持仓 {ex['curr_buy']}~{ex['curr_sell']}, 新买入 {ex['next_buy']}")
    
    return all_trades, signal_count_by_stock, signal_count_by_date


def main():
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    analyze_trades(data, start_date, end_date)


if __name__ == "__main__":
    main()
