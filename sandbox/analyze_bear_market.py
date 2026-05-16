"""
分析策略在熊市表现不佳的原因
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from collections import defaultdict
from numba import njit

from data_cache import get_cache


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


def analyze_trades(data, start_date, end_date):
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
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'buy_price': buy_price,
                    'close': close,
                    'high': high,
                    'buy_idx': buy_date_idx,
                })
    
    return all_trades


def main():
    print("=" * 70)
    print("分析策略在熊市表现不佳的原因")
    print("=" * 70)
    
    data = get_cache()
    
    print("\n" + "=" * 70)
    print("1. 按年度分析交易表现")
    print("=" * 70)
    
    periods = [
        ("2024-01-01", "2024-12-31", "2024年(熊市)"),
        ("2025-01-01", "2025-12-31", "2025年(牛市)"),
    ]
    
    for start_date, end_date, period_name in periods:
        trades = analyze_trades(data, start_date, end_date)
        
        if not trades:
            print(f"\n{period_name}: 无交易")
            continue
        
        returns = []
        for t in trades:
            close = t['close']
            high = t['high']
            buy_idx = t['buy_idx']
            buy_price = t['buy_price']
            
            sell_price = buy_price
            peak_price = buy_price
            triggered_trailing = False
            
            for hold_day in range(10):
                check_idx = buy_idx + hold_day
                if check_idx >= len(close):
                    check_idx = len(close) - 1
                    sell_price = close[check_idx]
                    break
                
                if high[check_idx] > peak_price:
                    peak_price = high[check_idx]
                
                day_high_pct = (high[check_idx] - buy_price) / buy_price
                
                if day_high_pct >= 0.03:
                    triggered_trailing = True
                
                if triggered_trailing:
                    drawdown = (peak_price - close[check_idx]) / peak_price
                    if drawdown >= 0.02:
                        sell_price = close[check_idx]
                        break
                
                if hold_day == 9:
                    sell_price = close[check_idx]
            
            ret = (sell_price - buy_price) / buy_price
            returns.append(ret)
        
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        
        total_return = sum(returns) * 100
        win_rate = len(wins) / len(returns) * 100
        avg_return = np.mean(returns) * 100
        profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
        
        print(f"\n{period_name}:")
        print(f"  交易次数: {len(trades)}")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  盈亏比: {profit_factor:.2f}")
        print(f"  平均收益: {avg_return:.2f}%")
        print(f"  总收益(累计): {total_return:.1f}%")
    
    print("\n" + "=" * 70)
    print("2. 分析买入后持仓期间的收益分布")
    print("=" * 70)
    
    trades_2024 = analyze_trades(data, "2024-01-01", "2024-12-31")
    trades_2025 = analyze_trades(data, "2025-01-01", "2025-12-31")
    
    for year_name, trades in [("2024年", trades_2024), ("2025年", trades_2025)]:
        print(f"\n{year_name}买入后各天收益分布:")
        
        hold_day_stats = defaultdict(list)
        
        for t in trades:
            close = t['close']
            buy_idx = t['buy_idx']
            buy_price = t['buy_price']
            
            for day in range(1, 11):
                check_idx = buy_idx + day
                if check_idx < len(close):
                    ret = (close[check_idx] - buy_price) / buy_price
                    hold_day_stats[day].append(ret)
        
        print(f"{'天数':^6} {'平均收益%':^10} {'正收益比例%':^12} {'中位数%':^10}")
        print("-" * 45)
        
        for day in range(1, 11):
            returns = hold_day_stats[day]
            if returns:
                avg_ret = np.mean(returns) * 100
                pos_ratio = len([r for r in returns if r > 0]) / len(returns) * 100
                median_ret = np.median(returns) * 100
                print(f"{day:^6} {avg_ret:^10.2f} {pos_ratio:^12.1f} {median_ret:^10.2f}")
    
    print("\n" + "=" * 70)
    print("3. 分析止盈触发情况")
    print("=" * 70)
    
    for year_name, trades in [("2024年", trades_2024), ("2025年", trades_2025)]:
        triggered_count = 0
        triggered_returns = []
        not_triggered_returns = []
        
        for t in trades:
            close = t['close']
            high = t['high']
            buy_idx = t['buy_idx']
            buy_price = t['buy_price']
            
            max_high = buy_price
            triggered = False
            sell_price = buy_price
            peak_price = buy_price
            
            for hold_day in range(10):
                check_idx = buy_idx + hold_day
                if check_idx >= len(close):
                    check_idx = len(close) - 1
                    sell_price = close[check_idx]
                    break
                
                if high[check_idx] > peak_price:
                    peak_price = high[check_idx]
                
                day_high_pct = (high[check_idx] - buy_price) / buy_price
                
                if day_high_pct >= 0.03:
                    triggered = True
                
                if triggered:
                    drawdown = (peak_price - close[check_idx]) / peak_price
                    if drawdown >= 0.02:
                        sell_price = close[check_idx]
                        break
                
                if hold_day == 9:
                    sell_price = close[check_idx]
            
            ret = (sell_price - buy_price) / buy_price
            
            if triggered:
                triggered_count += 1
                triggered_returns.append(ret)
            else:
                not_triggered_returns.append(ret)
        
        total = len(trades)
        print(f"\n{year_name}:")
        print(f"  总交易: {total}")
        print(f"  触发止盈: {triggered_count} ({triggered_count/total*100:.1f}%)")
        
        if triggered_returns:
            print(f"    触发止盈交易平均收益: {np.mean(triggered_returns)*100:.2f}%")
            print(f"    触发止盈交易胜率: {len([r for r in triggered_returns if r > 0])/len(triggered_returns)*100:.1f}%")
        
        if not_triggered_returns:
            print(f"  未触发止盈: {total - triggered_count} ({(total-triggered_count)/total*100:.1f}%)")
            print(f"    未触发止盈交易平均收益: {np.mean(not_triggered_returns)*100:.2f}%")
            print(f"    未触发止盈交易胜率: {len([r for r in not_triggered_returns if r > 0])/len(not_triggered_returns)*100:.1f}%")


if __name__ == "__main__":
    main()
