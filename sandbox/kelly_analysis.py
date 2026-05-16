"""
凯利公式计算最优仓位
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from collections import defaultdict
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


def kelly_criterion(win_rate: float, profit_loss_ratio: float) -> float:
    """
    凯利公式计算最优仓位
    
    f* = p - (1-p)/b
    
    Args:
        win_rate: 胜率 (0-1)
        profit_loss_ratio: 盈亏比 (平均盈利/平均亏损)
    
    Returns:
        最优仓位比例 (0-1)
    """
    p = win_rate
    b = profit_loss_ratio
    q = 1 - p
    
    kelly = p - q / b
    return max(0, kelly)


def run_backtest_for_kelly(data: PreloadedData, start_date: str, end_date: str,
                           max_hold_days: int = 10, take_profit_pct: float = 0.03,
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
                    'return': ret
                })
    
    return all_trades


def main():
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("=" * 70)
    print("凯利公式计算最优仓位")
    print("=" * 70)
    
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    all_trades = run_backtest_for_kelly(data, start_date, end_date)
    
    returns = [t['return'] for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    win_rate = len(wins) / len(returns)
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    print(f"\n策略统计:")
    print(f"  总交易次数: {len(returns)}")
    print(f"  盈利次数: {len(wins)}")
    print(f"  亏损次数: {len(losses)}")
    print(f"  胜率: {win_rate*100:.2f}%")
    print(f"  平均盈利: {avg_win*100:.2f}%")
    print(f"  平均亏损: {avg_loss*100:.2f}%")
    print(f"  盈亏比: {profit_loss_ratio:.2f}")
    
    kelly_full = kelly_criterion(win_rate, profit_loss_ratio)
    kelly_half = kelly_full / 2
    kelly_quarter = kelly_full / 4
    
    print(f"\n凯利公式计算:")
    print(f"  f* = p - (1-p)/b")
    print(f"  f* = {win_rate:.4f} - {(1-win_rate):.4f}/{profit_loss_ratio:.2f}")
    print(f"  f* = {win_rate:.4f} - {(1-win_rate)/profit_loss_ratio:.4f}")
    print(f"  f* = {kelly_full*100:.2f}%")
    
    print(f"\n建议仓位:")
    print(f"  全凯利仓位: {kelly_full*100:.2f}% (风险较高)")
    print(f"  半凯利仓位: {kelly_half*100:.2f}% (推荐)")
    print(f"  1/4凯利仓位: {kelly_quarter*100:.2f}% (保守)")
    
    print(f"\n持仓数量建议:")
    print(f"  当前策略: 单股2%仓位, 最多40只")
    print(f"  全凯利建议: 单股{kelly_full*100:.1f}%仓位, 最多{int(100/kelly_full/100)}只")
    print(f"  半凯利建议: 单股{kelly_half*100:.1f}%仓位, 最多{int(100/kelly_half/100)}只")
    print(f"  1/4凯利建议: 单股{kelly_quarter*100:.1f}%仓位, 最多{int(100/kelly_quarter/100)}只")
    
    print(f"\n考虑相关性的调整:")
    print(f"  股票之间有相关性，需要降低仓位")
    print(f"  假设平均相关系数为0.3，调整系数约 1/(1+0.3*(n-1))")
    
    for n in [10, 15, 20, 25, 30]:
        corr = 0.3
        adj_factor = 1 / (1 + corr * (n - 1))
        adj_kelly = kelly_half * adj_factor
        total_position = adj_kelly * n
        print(f"  持仓{n}只: 调整后单仓{adj_kelly*100:.1f}%, 总仓位{total_position*100:.1f}%")
    
    print(f"\n推荐配置:")
    optimal_n = 15
    corr = 0.3
    adj_factor = 1 / (1 + corr * (optimal_n - 1))
    adj_kelly = kelly_half * adj_factor
    print(f"  持仓数量: {optimal_n}只")
    print(f"  单股仓位: {adj_kelly*100:.1f}%")
    print(f"  总仓位上限: {adj_kelly*optimal_n*100:.1f}%")


if __name__ == "__main__":
    main()
