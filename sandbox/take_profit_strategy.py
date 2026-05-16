"""
止盈3%策略测试
- 买入：绿柱凹函数收缩信号次日收盘买入
- 止盈：持有期间涨幅达到3%时，当天收盘卖出
- 不止损：一直持有到最大持仓天数
"""

import numpy as np
from numba import njit
from data_cache import get_cache, PreloadedData


@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    """计算EMA"""
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    multiplier = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema


@njit
def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """计算MACD"""
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return dif, dea, histogram


@njit
def detect_signal(bars: np.ndarray) -> np.ndarray:
    """
    检测绿柱凹函数收缩信号
    条件：
    1. 连续4根绿柱（负值）
    2. 绿柱收缩（绝对值递减）
    3. 第4根绿柱 > -0.005（接近0）
    """
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
def backtest_take_profit(
    signals: np.ndarray,
    close: np.ndarray,
    high: np.ndarray,
    take_profit_pct: float,
    max_hold_days: int
) -> tuple:
    """
    止盈策略回测
    
    参数：
    - take_profit_pct: 止盈比例，如0.03表示3%
    - max_hold_days: 最大持仓天数
    """
    trades = []
    n = len(signals)
    i = 0
    
    while i < n - 1:
        if signals[i]:
            buy_date = i + 1
            if buy_date >= n:
                break
            
            buy_price = close[buy_date]
            
            sell_price = close[buy_date]
            sell_date = buy_date
            hit_take_profit = False
            
            for hold_day in range(max_hold_days):
                check_date = buy_date + hold_day
                if check_date >= n:
                    check_date = n - 1
                    sell_price = close[check_date]
                    sell_date = check_date
                    break
                
                day_high_pct = (high[check_date] - buy_price) / buy_price
                
                if day_high_pct >= take_profit_pct:
                    sell_price = close[check_date]
                    sell_date = check_date
                    hit_take_profit = True
                    break
                
                if hold_day == max_hold_days - 1:
                    sell_price = close[check_date]
                    sell_date = check_date
            
            ret = (sell_price - buy_price) / buy_price
            hold_days = sell_date - buy_date + 1
            trades.append((ret, hold_days, hit_take_profit))
            
            i = sell_date + 1
        else:
            i += 1
    
    return trades


def run_strategy(data: PreloadedData, start_date: str, end_date: str, 
                 take_profit_pct: float, max_hold_days: int):
    """运行策略"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = d['close'][mask]
        high = d['high'][mask]
        
        if len(close) < 30:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        trades = backtest_take_profit(signals, close, high, take_profit_pct, max_hold_days)
        all_trades.extend(trades)
    
    return all_trades


def print_stats(trades: list, take_profit_pct: float, max_hold_days: int):
    """打印统计"""
    if not trades:
        print("  无交易")
        return
    
    returns = np.array([t[0] for t in trades])
    hold_days = np.array([t[1] for t in trades])
    hit_tp = np.array([t[2] for t in trades])
    
    wins = returns > 0
    losses = returns < 0
    
    total_profit = np.sum(returns[wins])
    total_loss = abs(np.sum(returns[losses]))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    tp_trades = returns[hit_tp]
    non_tp_trades = returns[~hit_tp]
    
    print(f"\n止盈{take_profit_pct*100:.0f}%，最大持仓{max_hold_days}天:")
    print(f"  总交易数: {len(trades)}")
    print(f"  胜率: {np.mean(wins)*100:.1f}%")
    print(f"  平均收益: {np.mean(returns)*100:.2f}%")
    print(f"  盈利因子: {profit_factor:.2f}")
    print(f"  平均持仓: {np.mean(hold_days):.1f}天")
    print(f"\n  触发止盈: {np.sum(hit_tp)}笔 ({np.mean(hit_tp)*100:.1f}%)")
    print(f"    平均收益: {np.mean(tp_trades)*100:.2f}%" if len(tp_trades) > 0 else "    无")
    print(f"  未触发止盈: {np.sum(~hit_tp)}笔 ({np.mean(~hit_tp)*100:.1f}%)")
    print(f"    平均收益: {np.mean(non_tp_trades)*100:.2f}%" if len(non_tp_trades) > 0 else "    无")


def main():
    print("=" * 70)
    print("止盈3%策略测试")
    print("=" * 70)
    print("\n策略逻辑：")
    print("  - 买入：绿柱凹函数收缩信号次日收盘买入")
    print("  - 止盈：持有期间涨幅达到3%时，当天收盘卖出")
    print("  - 不止损：一直持有到最大持仓天数")
    
    data = get_cache()
    
    print("\n" + "=" * 70)
    print("测试不同止盈比例和最大持仓天数")
    print("=" * 70)
    
    test_cases = [
        (0.03, 5),
        (0.03, 10),
        (0.03, 20),
        (0.02, 10),
        (0.04, 10),
        (0.05, 10),
    ]
    
    for tp_pct, max_days in test_cases:
        trades = run_strategy(data, "2025-01-01", "2025-10-31", tp_pct, max_days)
        print_stats(trades, tp_pct, max_days)
    
    print("\n" + "=" * 70)
    print("详细分析：止盈3%，最大持仓10天")
    print("=" * 70)
    
    trades = run_strategy(data, "2025-01-01", "2025-10-31", 0.03, 10)
    
    if trades:
        returns = np.array([t[0] for t in trades])
        hold_days = np.array([t[1] for t in trades])
        hit_tp = np.array([t[2] for t in trades])
        
        print(f"\n收益分布：")
        print(f"  >5%: {np.sum(returns > 0.05)}笔")
        print(f"  3-5%: {np.sum((returns >= 0.03) & (returns <= 0.05))}笔")
        print(f"  0-3%: {np.sum((returns >= 0) & (returns < 0.03))}笔")
        print(f"  -3-0%: {np.sum((returns >= -0.03) & (returns < 0))}笔")
        print(f"  -5--3%: {np.sum((returns >= -0.05) & (returns < -0.03))}笔")
        print(f"  <-5%: {np.sum(returns < -0.05)}笔")
        
        print(f"\n持仓天数分布：")
        for d in range(1, 11):
            count = np.sum(hold_days == d)
            avg_ret = np.mean(returns[hold_days == d]) * 100 if count > 0 else 0
            print(f"  {d}天: {count}笔, 平均收益: {avg_ret:.2f}%")


if __name__ == "__main__":
    main()
