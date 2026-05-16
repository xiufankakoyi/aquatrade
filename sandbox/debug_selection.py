"""
调试：对比两个脚本的差异
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from collections import defaultdict
from numba import njit

from data_cache import get_cache


@njit
def calc_ema(arr, period):
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
    return ema


@njit
def calc_macd(close):
    ema_fast = calc_ema(close, 12)
    ema_slow = calc_ema(close, 26)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, 9)
    return (dif - dea) * 2


@njit
def detect_signal(bars):
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3):
                if b3 > -0.005:
                    signals[i] = True
    return signals


def main():
    print("=" * 70)
    print("调试：分析选股问题")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    all_trades = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        hist = calc_macd(close)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        hist = hist[mask]
        signals = signals[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                
                sell_price = buy_price
                peak_price = buy_price
                triggered = False
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
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
                        dd = (peak_price - close[check_idx]) / peak_price
                        if dd >= 0.02:
                            sell_price = close[check_idx]
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'return': ret,
                })
    
    print(f"\n总信号数: {len(all_trades)}")
    
    trades_by_date = defaultdict(list)
    for t in all_trades:
        trades_by_date[t['buy_date']].append(t)
    
    print(f"总交易日: {len(trades_by_date)}")
    
    print(f"\n前10天每天信号数:")
    for date in sorted(trades_by_date.keys())[:10]:
        trades = trades_by_date[date]
        trades.sort(key=lambda x: x['stock_code'])
        
        print(f"\n  {date}: {len(trades)}个信号")
        print(f"    选中的5只: {[t['stock_code'] for t in trades[:5]]}")
        print(f"    收益率: {[t['return']*100 for t in trades[:5]]}")
        
        if len(trades) > 5:
            rest_returns = [t['return'] for t in trades[5:]]
            print(f"    未选中的{len(trades)-5}只平均收益: {np.mean(rest_returns)*100:.1f}%")
    
    print("\n" + "=" * 70)
    print("模拟实际资金管理")
    print("=" * 70)
    
    for date in trades_by_date:
        trades_by_date[date].sort(key=lambda x: x['stock_code'])
    
    capital = 100000.0
    holdings = {}
    
    all_dates = sorted(set(t['buy_date'] for t in all_trades) | set(t['sell_date'] for t in all_trades))
    
    for date in all_dates:
        for code in list(holdings.keys()):
            if holdings[code]['sell_date'] == date:
                profit = holdings[code]['pos_val'] * holdings[code]['return']
                capital += profit
                del holdings[code]
        
        if date in trades_by_date:
            for t in trades_by_date[date]:
                if t['stock_code'] not in holdings and len(holdings) < 5:
                    holdings[t['stock_code']] = {
                        'pos_val': capital * 0.18,
                        'return': t['return'],
                        'sell_date': str(date),
                    }
    
    for code in list(holdings.keys()):
        capital += holdings[code]['pos_val'] * holdings[code]['return']
    
    print(f"\n最终资金: {capital:.0f}")
    print(f"总收益: {(capital - 100000) / 100000 * 100:.1f}%")


if __name__ == "__main__":
    main()
