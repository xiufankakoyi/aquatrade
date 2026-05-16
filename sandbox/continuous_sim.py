"""
正确的连续模拟 - 2024-2025
"""

import numpy as np
from numba import njit
from data_cache import get_cache, PreloadedData
from collections import defaultdict


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


def main():
    print("=" * 70)
    print("2024-2025 连续模拟")
    print("=" * 70)
    
    print("\n策略：止盈3%，最大持仓10天，单股10%，总仓80%")
    
    data = get_cache()
    
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= "2024-01-01") & (dates <= "2025-12-31")
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
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
                sell_price = buy_price
                sell_date = buy_date
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= 0.03:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret
                })
    
    print(f"\n总交易数: {len(all_trades)}")
    
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
    capital_history = []
    peak = capital
    max_dd = 0
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * 0.10
            
            for t in trades_by_buy_date[date]:
                if current_position_pct + 0.10 <= 0.80:
                    holdings[t['stock_code']] = {
                        'position_value': capital * 0.10,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position_pct += 0.10
        
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak
        if dd > max_dd:
            max_dd = dd
        
        capital_history.append((date, capital))
    
    for stock_code in holdings:
        capital += holdings[stock_code]['position_value'] * holdings[stock_code]['return']
    
    print(f"\n初始资金: 100,000")
    print(f"最终资金: {capital:,.0f}")
    print(f"总收益: {(capital-100000)/100000*100:.1f}%")
    print(f"最大回撤: {max_dd*100:.1f}%")
    
    print("\n资金曲线（每月初）：")
    prev_month = ""
    for date, cap in capital_history:
        month = date[:7]
        if month != prev_month:
            print(f"  {month}: {cap:,.0f}")
            prev_month = month
    
    print("\n按年份统计：")
    for year in ['2024', '2025']:
        year_trades = [t for t in all_trades if t['buy_date'].startswith(year)]
        if year_trades:
            returns = np.array([t['return'] for t in year_trades])
            wins = returns > 0
            print(f"\n{year}年:")
            print(f"  交易数: {len(year_trades)}")
            print(f"  胜率: {np.mean(wins)*100:.1f}%")
            print(f"  平均收益: {np.mean(returns)*100:.2f}%")
            print(f"  盈利因子: {np.sum(returns[wins])/abs(np.sum(returns[~wins])):.2f}")


if __name__ == "__main__":
    main()
