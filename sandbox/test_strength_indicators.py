"""
验证多种信号强度指标的有效性
1. 最后一天绿柱值：绿柱越接近0，信号越强
2. 绿柱收缩幅度：(绿柱1绝对值 - 绿柱4绝对值)/绿柱1绝对值
3. 绿柱面积：最近4天绿柱绝对值之和
4. 成交量变化：当日成交量相比过去5日均值的增幅
5. 行业龙头：下跌趋势中最抗跌的品种
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
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


def main():
    print("=" * 70)
    print("验证多种信号强度指标的有效性")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    all_signals = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 100:
            continue
        
        hist = calc_macd(close)
        signals = detect_signal(hist)
        
        vol_ma5 = np.zeros(len(volume))
        for v in range(5, len(volume)):
            vol_ma5[v] = np.mean(volume[v-5:v])
        vol_ma5[:5] = volume[:5]
        
        ma20 = np.zeros(len(close))
        for i in range(20, len(close)):
            ma20[i] = np.mean(close[i-20:i])
        ma20[:20] = close[:20]
        
        ret_20d = np.zeros(len(close))
        for i in range(len(close) - 20):
            ret_20d[i] = (close[i+20] - close[i]) / close[i]
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        hist = hist[mask]
        signals = signals[mask]
        volume = volume[mask]
        vol_ma5 = vol_ma5[mask]
        ma20 = ma20[mask]
        ret_20d = ret_20d[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                last_bar = abs(hist[i])
                
                bar1 = abs(hist[i-3])
                bar4 = abs(hist[i])
                if bar1 > 0:
                    contraction = (bar1 - bar4) / bar1
                else:
                    contraction = 0
                
                bar_area = abs(hist[i-3]) + abs(hist[i-2]) + abs(hist[i-1]) + abs(hist[i])
                
                if vol_ma5[i] > 0:
                    vol_change = volume[i] / vol_ma5[i]
                else:
                    vol_change = 1.0
                
                if ma20[i] > 0:
                    price_vs_ma = (close[i] - ma20[i]) / ma20[i]
                else:
                    price_vs_ma = 0
                
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
                
                all_signals.append({
                    'stock_code': stock_code,
                    'buy_date': str(dates[buy_date_idx]),
                    'return': ret,
                    'last_bar': last_bar,
                    'contraction': contraction,
                    'bar_area': bar_area,
                    'vol_change': vol_change,
                    'price_vs_ma': price_vs_ma,
                })
    
    print(f"\n总信号数: {len(all_signals)}")
    
    def analyze_indicator(signals, indicator_name, indicator_key, ascending=False):
        """分析单个指标的有效性"""
        print(f"\n{'=' * 70}")
        print(f"指标: {indicator_name}")
        print("=" * 70)
        
        sorted_signals = sorted(signals, key=lambda x: x[indicator_key])
        
        n = len(sorted_signals)
        group_size = n // 4
        
        groups = [
            ("最弱(后25%)", sorted_signals[:group_size]),
            ("较弱(25%-50%)", sorted_signals[group_size:group_size*2]),
            ("较强(50%-75%)", sorted_signals[group_size*2:group_size*3]),
            ("最强(前25%)", sorted_signals[group_size*3:]),
        ]
        
        if ascending:
            groups = groups[::-1]
            groups = [
                ("最强(前25%)", groups[0][1]),
                ("较强(50%-75%)", groups[1][1]),
                ("较弱(25%-50%)", groups[2][1]),
                ("最弱(后25%)", groups[3][1]),
            ]
        
        print(f"\n{'分组':^15} {'信号数':^8} {'胜率%':^8} {'平均收益%':^10} {'盈亏比':^8}")
        print("-" * 55)
        
        results = []
        for group_name, group_signals in groups:
            returns = [s['return'] for s in group_signals]
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r < 0]
            
            win_rate = len(wins) / len(returns) * 100 if returns else 0
            avg_ret = np.mean(returns) * 100 if returns else 0
            pf = sum(wins) / abs(sum(losses)) if losses else float('inf')
            
            print(f"{group_name:^15} {len(returns):^8} {win_rate:^8.1f} {avg_ret:^10.2f} {pf:^8.2f}")
            results.append((group_name, win_rate, avg_ret, pf))
        
        strongest = results[0]
        weakest = results[-1]
        diff = strongest[2] - weakest[2]
        
        print(f"\n最强vs最弱收益差: {diff:.2f}%")
        if diff > 0.5:
            print(f"结论: 该指标有预测能力，建议使用")
        elif diff > 0:
            print(f"结论: 该指标预测能力较弱")
        else:
            print(f"结论: 该指标无预测能力，不建议使用")
        
        return diff
    
    analyze_indicator(all_signals, "最后一天绿柱值(越接近0越强)", 'last_bar', ascending=True)
    analyze_indicator(all_signals, "绿柱收缩幅度(越大越强)", 'contraction', ascending=False)
    analyze_indicator(all_signals, "绿柱面积(越小越强)", 'bar_area', ascending=True)
    analyze_indicator(all_signals, "成交量变化(越大越强)", 'vol_change', ascending=False)
    analyze_indicator(all_signals, "价格相对MA20(越低越强)", 'price_vs_ma', ascending=True)
    
    print("\n" + "=" * 70)
    print("综合分析")
    print("=" * 70)
    
    print("""
根据以上分析结果，选择预测能力最强的指标作为信号强度排序依据。

如果多个指标都有预测能力，可以考虑组合使用：
  综合强度 = 指标1得分 + 指标2得分 + ...

如果所有指标都无预测能力，则保持按股票代码排序。
""")


if __name__ == "__main__":
    main()
