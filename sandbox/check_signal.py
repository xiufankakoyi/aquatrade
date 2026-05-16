"""检查1月2日信号"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from numba import njit
from sandbox.data_cache import get_cache


@njit
def calc_ema(arr, period):
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    multiplier = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema


@njit
def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return histogram


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
    data = get_cache()
    
    # 检查所有股票在1月2日到1月5日的信号
    stock_codes = sorted(data.daily_data.keys())
    
    signals_by_date = {}
    
    for stock_code in stock_codes[:100]:  # 先检查前100只
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        
        if len(close) < 50:
            continue
        
        # 过滤2024年数据
        mask = (dates >= '2024-01-01') & (dates <= '2024-12-31')
        close_filtered = close[mask]
        dates_filtered = dates[mask]
        
        if len(close_filtered) < 50:
            continue
        
        hist = calc_macd(close_filtered)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_idx = i + 1
                if buy_idx < len(dates_filtered):
                    buy_date = str(dates_filtered[buy_idx])
                    if buy_date not in signals_by_date:
                        signals_by_date[buy_date] = []
                    signals_by_date[buy_date].append(stock_code)
                    break  # 只记录第一个信号
    
    print("各买入日期的信号股票数:")
    for date in sorted(signals_by_date.keys())[:10]:
        print(f"  {date}: {len(signals_by_date[date])} 只")


if __name__ == '__main__':
    main()
