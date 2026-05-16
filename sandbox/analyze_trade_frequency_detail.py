"""
详细分析交易频率
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


def analyze_trade_frequency_detail(data: PreloadedData, start_date: str, end_date: str,
                   position_per_stock: float = 0.02, max_total_position: float = 0.80,
                   take_profit_pct: float = 0.03, max_hold_days: int = 10,
                   trailing_pct: float = 0.02):
    
    all_trades = []
    
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
                hold_days_count = 0
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                        hold_days_count = hold_day
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
                            hold_days_count = hold_day + 1
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                        hold_days_count = max_hold_days
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret,
                    'hold_days': hold_days_count
                })
    
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
    
    daily_stats = []
    
    for date in all_dates:
        daily_bought = 0
        daily_sold = 0
        daily_rejected_position = 0
        daily_rejected_duplicate = 0
        
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
                    'hold_days': h['hold_days']
                })
                del holdings[stock_code]
                daily_sold += 1
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    rejected_by_duplicate += 1
                    daily_rejected_duplicate += 1
                    continue
                
                if current_position_pct + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                        'buy_date': t['buy_date'],
                        'hold_days': t['hold_days']
                    }
                    current_position_pct += position_per_stock
                    daily_bought += 1
                else:
                    rejected_by_position += 1
                    daily_rejected_position += 1
        
        daily_stats.append({
            'date': date,
            'holdings_count': len(holdings),
            'bought': daily_bought,
            'sold': daily_sold,
            'rejected_position': daily_rejected_position,
            'rejected_duplicate': daily_rejected_duplicate,
            'signals': len(trades_by_buy_date.get(date, []))
        })
        
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
            'hold_days': h['hold_days']
        })
    
    print("=" * 70)
    print("交易频率详细分析")
    print("=" * 70)
    
    print(f"\n生成的信号总数: {len(all_trades)}")
    print(f"实际执行的交易数: {len(executed_trades)}")
    print(f"因仓位上限拒绝: {rejected_by_position}")
    print(f"因重复持仓拒绝: {rejected_by_duplicate}")
    
    df_stats = pd.DataFrame(daily_stats)
    
    print(f"\n每日持仓数量统计:")
    print(f"  平均持仓: {df_stats['holdings_count'].mean():.1f} 只")
    print(f"  最大持仓: {df_stats['holdings_count'].max()} 只")
    print(f"  最小持仓: {df_stats['holdings_count'].min()} 只")
    
    print(f"\n每日买入统计:")
    print(f"  平均买入: {df_stats['bought'].mean():.2f} 只/天")
    print(f"  最大买入: {df_stats['bought'].max()} 只/天")
    print(f"  买入>0的天数: {(df_stats['bought'] > 0).sum()} 天")
    
    print(f"\n每日卖出统计:")
    print(f"  平均卖出: {df_stats['sold'].mean():.2f} 只/天")
    print(f"  最大卖出: {df_stats['sold'].max()} 只/天")
    
    print(f"\n每日被拒统计:")
    print(f"  因仓位拒绝平均: {df_stats['rejected_position'].mean():.2f} 只/天")
    print(f"  因仓位拒绝最多: {df_stats['rejected_position'].max()} 只/天")
    
    df_trades = pd.DataFrame(executed_trades)
    print(f"\n实际持仓天数(交易日)统计:")
    print(f"  最小: {df_trades['hold_days'].min()}")
    print(f"  最大: {df_trades['hold_days'].max()}")
    print(f"  平均: {df_trades['hold_days'].mean():.2f}")
    print(f"  中位数: {df_trades['hold_days'].median():.0f}")
    
    print(f"\n持仓天数分布:")
    for days in sorted(df_trades['hold_days'].unique()):
        count = len(df_trades[df_trades['hold_days'] == days])
        print(f"  {days}天: {count}次 ({count/len(df_trades)*100:.1f}%)")
    
    return executed_trades, df_stats


def main():
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    analyze_trade_frequency_detail(data, start_date, end_date)


if __name__ == "__main__":
    main()
