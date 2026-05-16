"""
测试多种信号强度指标
1. 收缩速度：绿柱收缩的加速度（abs(b0)-abs(b3)）
2. RSI配合：信号日RSI是否超卖（RSI<30更强）
3. 成交量配合：信号日成交量是否放大
4. 价格位置：是否在均线支撑位附近
5. 多周期确认：多个时间周期的MACD是否同时收缩
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
def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    return dif, dea, (dif - dea) * 2


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


def run_backtest_with_strength(data, start_date, end_date, strength_type='none'):
    """
    运行回测，使用不同的信号强度指标
    
    strength_type:
        'none': 不排序
        'contraction_speed': 收缩速度（abs(b0)-abs(b3)）
        'rsi_oversold': RSI超卖程度（RSI越低越强）
        'volume_surge': 成交量放大程度
        'ma_support': 均线支撑程度
        'multi_timeframe': 多周期确认
    """
    all_trades = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 100:
            continue
        
        dif, dea, hist = calc_macd(close)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        signals = detect_signal(hist)
        
        ma20 = np.zeros(len(close))
        ma60 = np.zeros(len(close))
        for i in range(20, len(close)):
            ma20[i] = np.mean(close[i-20:i])
        for i in range(60, len(close)):
            ma60[i] = np.mean(close[i-60:i])
        ma20[:20] = close[:20]
        ma60[:60] = close[:60]
        
        vol_ma5 = np.zeros(len(volume))
        for i in range(5, len(volume)):
            vol_ma5[i] = np.mean(volume[i-5:i])
        vol_ma5[:5] = volume[:5]
        
        _, _, hist_week = calc_macd(close, fast=24, slow=52, signal=18)
        
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
        volume = volume[mask]
        vol_ma5 = vol_ma5[mask]
        ma20 = ma20[mask]
        ma60 = ma60[mask]
        hist_week = hist_week[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                strength = 0.0
                
                if strength_type == 'contraction_speed':
                    b0, b3 = abs(hist[i-3]), abs(hist[i])
                    strength = b0 - b3
                
                elif strength_type == 'rsi_oversold':
                    strength = 50 - rsi[i]
                
                elif strength_type == 'volume_surge':
                    if vol_ma5[i] > 0:
                        strength = volume[i] / vol_ma5[i]
                    else:
                        strength = 1.0
                
                elif strength_type == 'ma_support':
                    if ma20[i] > 0:
                        strength = (ma20[i] - close[i]) / ma20[i] * 100
                    else:
                        strength = 0.0
                
                elif strength_type == 'multi_timeframe':
                    if hist_week[i] < 0 and abs(hist_week[i]) < abs(hist_week[i-5]):
                        strength = 2.0
                    elif hist_week[i] < 0:
                        strength = 1.0
                    else:
                        strength = 0.0
                
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
                    'strength': strength,
                })
    
    all_dates = sorted(set(t['buy_date'] for t in all_trades) | set(t['sell_date'] for t in all_trades))
    
    trades_by_date = defaultdict(list)
    for t in all_trades:
        trades_by_date[t['buy_date']].append(t)
    
    if strength_type != 'none':
        for date in trades_by_date:
            trades_by_date[date].sort(key=lambda x: x['strength'], reverse=True)
    
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


def analyze_strength_groups(trades, strength_type):
    """按信号强度分组分析"""
    if strength_type == 'none':
        return
    
    strength_groups = defaultdict(list)
    
    for t in trades:
        s = t['strength']
        
        if strength_type == 'contraction_speed':
            if s > 0.03:
                group = "极强(>0.03)"
            elif s > 0.02:
                group = "强(0.02~0.03)"
            elif s > 0.01:
                group = "中(0.01~0.02)"
            else:
                group = "弱(<0.01)"
        
        elif strength_type == 'rsi_oversold':
            if s > 20:
                group = "极强(RSI<30)"
            elif s > 10:
                group = "强(RSI30~40)"
            elif s > 0:
                group = "中(RSI40~50)"
            else:
                group = "弱(RSI>50)"
        
        elif strength_type == 'volume_surge':
            if s > 2.0:
                group = "极强(>2倍)"
            elif s > 1.5:
                group = "强(1.5~2倍)"
            elif s > 1.0:
                group = "中(1~1.5倍)"
            else:
                group = "弱(<1倍)"
        
        elif strength_type == 'ma_support':
            if s > 5:
                group = "极强(>5%)"
            elif s > 2:
                group = "强(2~5%)"
            elif s > 0:
                group = "中(0~2%)"
            else:
                group = "弱(<0%)"
        
        elif strength_type == 'multi_timeframe':
            if s >= 2:
                group = "极强(双周期确认)"
            elif s >= 1:
                group = "强(周线绿柱)"
            else:
                group = "弱(无确认)"
        
        else:
            return
        
        strength_groups[group].append(t['return'])
    
    print(f"\n  强度分组分析:")
    print(f"  {'强度':^20} {'交易数':^8} {'胜率%':^8} {'平均收益%':^10}")
    print("  " + "-" * 50)
    
    for group, returns in strength_groups.items():
        wins = [r for r in returns if r > 0]
        win_rate = len(wins) / len(returns) * 100 if returns else 0
        avg_ret = np.mean(returns) * 100 if returns else 0
        print(f"  {group:^20} {len(returns):^8} {win_rate:^8.1f} {avg_ret:^10.2f}")


def main():
    print("=" * 70)
    print("多种信号强度指标对比测试")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    strategies = [
        ("策略1: 不排序(基准)", 'none'),
        ("策略2: 收缩速度", 'contraction_speed'),
        ("策略3: RSI超卖程度", 'rsi_oversold'),
        ("策略4: 成交量放大", 'volume_surge'),
        ("策略5: 均线支撑", 'ma_support'),
        ("策略6: 多周期确认", 'multi_timeframe'),
    ]
    
    print(f"\n{'策略':^25} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-" * 80)
    
    results = []
    for name, strength_type in strategies:
        equity, trades = run_backtest_with_strength(data, start_date, end_date, strength_type)
        m = calc_metrics(equity, trades)
        results.append((name, strength_type, m, trades))
        
        print(f"{name:^25} {m['trades']:^8} {m['win_rate']:^8.1f} {m['profit_factor']:^8.2f} {m['total_return']:^10.1f} {m['avg_return']:^10.2f}")
    
    print("\n" + "=" * 70)
    print("各策略强度分组分析")
    print("=" * 70)
    
    for name, strength_type, m, trades in results[1:]:
        print(f"\n{name}:")
        analyze_strength_groups(trades, strength_type)


if __name__ == "__main__":
    main()
