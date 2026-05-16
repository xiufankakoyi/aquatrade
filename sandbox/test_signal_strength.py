"""
对比测试：信号强度排序 vs 不排序
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
def calc_rsi(close, period=14):
    n = len(close)
    rsi = np.zeros(n)
    gains = np.zeros(n)
    losses = np.zeros(n)
    
    for i in range(1, n):
        change = close[i] - close[i-1]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = -change
    
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    for i in range(period, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    rsi[:period] = 50
    return rsi


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


@njit
def find_local_peaks(arr, window=5):
    n = len(arr)
    peaks = np.zeros(n, dtype=np.bool_)
    for i in range(window, n - window):
        is_peak = True
        for j in range(-window, window + 1):
            if j != 0 and arr[i] <= arr[i + j]:
                is_peak = False
                break
        peaks[i] = is_peak
    return peaks


def run_backtest(data, start_date, end_date, use_signal_strength=False, sort_ascending=False):
    """运行回测
    
    Args:
        use_signal_strength: 是否使用信号强度排序
        sort_ascending: False=强度高的优先(绿柱接近0), True=强度低的优先(绿柱绝对值大)
    """
    all_trades = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        hist = calc_macd(close)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        hist = hist[mask]
        rsi = rsi[mask]
        peaks = peaks[mask]
        signals = signals[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                signal_strength = -abs(hist[i])
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered = False
                sell_reason = "timeout"
                hold_days = 0
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = hold_day
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= 0.03:
                        triggered = True
                    
                    divergence = False
                    if peaks[check_idx]:
                        prev_peak = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak = j
                                break
                        
                        if prev_peak > 0 and close[check_idx] > close[prev_peak]:
                            if hist[check_idx] < hist[prev_peak]:
                                divergence = True
                            if rsi[check_idx] < rsi[prev_peak] and rsi[check_idx] > 75:
                                divergence = True
                    
                    if divergence and triggered:
                        sell_price = close[check_idx]
                        sell_reason = "divergence"
                        hold_days = hold_day + 1
                        break
                    
                    if triggered:
                        dd = (peak_price - close[check_idx]) / peak_price
                        if dd >= 0.02:
                            sell_price = close[check_idx]
                            sell_reason = "trailing_stop"
                            hold_days = hold_day + 1
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = 10
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': str(dates[min(buy_date_idx + hold_days - 1, len(close)-1)]),
                    'return': ret,
                    'signal_strength': signal_strength,
                })
    
    all_dates = sorted(set(t['buy_date'] for t in all_trades) | set(t['sell_date'] for t in all_trades))
    
    trades_by_date = defaultdict(list)
    for t in all_trades:
        trades_by_date[t['buy_date']].append(t)
    
    if use_signal_strength:
        for date in trades_by_date:
            trades_by_date[date].sort(key=lambda x: x['signal_strength'], reverse=not sort_ascending)
    
    capital = 100000.0
    holdings = {}
    equity = []
    
    for date in all_dates:
        for code in list(holdings.keys()):
            if holdings[code]['sell_date'] == date:
                capital += holdings[code]['pos_val'] * holdings[code]['return']
                del holdings[code]
        
        for t in trades_by_date[date]:
            if t['stock_code'] not in holdings and len(holdings) < 5:
                holdings[t['stock_code']] = {
                    'pos_val': capital * 0.18,
                    'return': t['return'],
                    'sell_date': t['sell_date'],
                }
        
        equity.append({'date': date, 'equity': capital})
    
    for code in list(holdings.keys()):
        capital += holdings[code]['pos_val'] * holdings[code]['return']
    
    return equity, all_trades


def calc_metrics(equity, trades):
    if not equity:
        return {}
    
    total_ret = (equity[-1]['equity'] - 100000) / 100000 * 100
    
    returns = [t['return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    pf = sum(wins) / abs(sum(losses)) if losses else float('inf')
    avg_ret = np.mean(returns) * 100 if returns else 0
    
    return {
        'total_return': total_ret,
        'win_rate': win_rate,
        'profit_factor': pf,
        'avg_return': avg_ret,
        'trades': len(trades),
    }


def main():
    print("=" * 70)
    print("信号强度排序对比测试")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    strategies = [
        ("策略1: 不排序(原策略)", False, False),
        ("策略2: 强度优先(绿柱接近0)", True, False),
        ("策略3: 强度靠后(绿柱绝对值大)", True, True),
    ]
    
    print(f"\n{'策略':^30} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-" * 80)
    
    for name, use_strength, ascending in strategies:
        equity, trades = run_backtest(data, start_date, end_date, use_strength, ascending)
        m = calc_metrics(equity, trades)
        print(f"{name:^30} {m['trades']:^8} {m['win_rate']:^8.1f} {m['profit_factor']:^8.2f} {m['total_return']:^10.1f} {m['avg_return']:^10.2f}")
    
    print("\n" + "=" * 70)
    print("信号强度分析")
    print("=" * 70)
    
    equity, trades = run_backtest(data, start_date, end_date, False, False)
    
    strength_groups = defaultdict(list)
    for t in trades:
        strength = t['signal_strength']
        if strength > -0.001:
            group = "极强(>-0.001)"
        elif strength > -0.002:
            group = "强(-0.001~-0.002)"
        elif strength > -0.003:
            group = "中(-0.002~-0.003)"
        else:
            group = "弱(<-0.003)"
        strength_groups[group].append(t['return'])
    
    print(f"\n{'信号强度':^20} {'交易数':^8} {'胜率%':^8} {'平均收益%':^10}")
    print("-" * 50)
    
    for group in ["极强(>-0.001)", "强(-0.001~-0.002)", "中(-0.002~-0.003)", "弱(<-0.003)"]:
        if group in strength_groups:
            returns = strength_groups[group]
            wins = [r for r in returns if r > 0]
            win_rate = len(wins) / len(returns) * 100
            avg_ret = np.mean(returns) * 100
            print(f"{group:^20} {len(returns):^8} {win_rate:^8.1f} {avg_ret:^10.2f}")


if __name__ == "__main__":
    main()
