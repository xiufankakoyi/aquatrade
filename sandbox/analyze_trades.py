"""分析原版策略的买入逻辑"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from numba import njit
from collections import defaultdict

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
    
    all_trades = []
    stock_codes = sorted(data.daily_data.keys())
    
    print(f"总股票数: {len(stock_codes)}")
    
    for stock_code in stock_codes:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        
        if len(close) < 50:
            continue
        
        mask = (dates >= '2024-01-01') & (dates <= '2024-01-31')
        if not np.any(mask):
            continue
        
        close = close[mask]
        dates = dates[mask]
        
        if len(close) < 50:
            continue
        
        hist = calc_macd(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx < len(dates):
                    buy_date = str(dates[buy_date_idx])
                    buy_price = close[buy_date_idx]
                    all_trades.append({
                        'stock_code': stock_code,
                        'buy_date': buy_date,
                        'buy_price': buy_price
                    })
                    break
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    sorted_dates = sorted(trades_by_buy_date.keys())
    print('\n前5个买入日期及股票:')
    for d in sorted_dates[:5]:
        print(f'{d}: {len(trades_by_buy_date[d])} 只股票')
        for t in trades_by_buy_date[d][:5]:
            print(f'  {t["stock_code"]} 价格: {t["buy_price"]:.2f}')
    
    print('\n模拟仓位管理 (最多5只):')
    holdings = {}
    for date in sorted_dates[:10]:
        print(f'\n日期: {date}')
        for t in trades_by_buy_date[date]:
            if t['stock_code'] in holdings:
                continue
            if len(holdings) < 5:
                holdings[t['stock_code']] = t
                print(f'  买入 {t["stock_code"]} 价格: {t["buy_price"]:.2f}')


if __name__ == '__main__':
    main()
