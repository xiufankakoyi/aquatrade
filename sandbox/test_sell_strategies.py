"""
卖点策略对比测试 - 7种不同卖点
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict

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
    return histogram


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


def run_backtest_strategy1(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct=0.03, max_hold_days=10):
    """策略1: 原策略 - 止盈3%，最大持仓10天"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
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
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'return': ret})
    
    return all_trades


def run_backtest_strategy2(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct=0.03, max_hold_days=5):
    """策略2: 缩短持仓 - 止盈3%，最大持仓5天"""
    return run_backtest_strategy1(data, start_date, end_date, position_per_stock, max_total_position,
                                   take_profit_pct, max_hold_days)


def run_backtest_strategy3(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct=0.03, max_hold_days=10, stop_loss_pct=0.05):
    """策略3: 添加止损 - 止盈3%，止损5%，最大持仓10天"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        low = d['low']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        low = low[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
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
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    day_low_pct = (low[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if day_low_pct <= -stop_loss_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'return': ret})
    
    return all_trades


def run_backtest_strategy4(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct=0.03, max_hold_days=10, trailing_pct=0.02):
    """策略4: 移动止盈 - 止盈3%后，回撤2%止盈"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
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
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
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
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'return': ret})
    
    return all_trades


def run_backtest_strategy5(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct=0.03, max_hold_days=10, time_stop_days=3):
    """策略5: 时间止损 - 3天内没涨到2%就卖"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
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
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day >= time_stop_days and day_high_pct < 0.02:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'return': ret})
    
    return all_trades


def run_backtest_strategy6(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           take_profit_pct1=0.02, take_profit_pct2=0.05, max_hold_days=10):
    """策略6: 分批止盈 - 2%卖一半，5%卖剩余"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                
                sold_half = False
                total_return = 0
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        if sold_half:
                            total_return += 0.5 * (close[check_idx] - buy_price) / buy_price
                        else:
                            total_return = (close[check_idx] - buy_price) / buy_price
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if not sold_half and day_high_pct >= take_profit_pct1:
                        total_return = 0.5 * (close[check_idx] - buy_price) / buy_price
                        sold_half = True
                    
                    if sold_half and day_high_pct >= take_profit_pct2:
                        total_return += 0.5 * (close[check_idx] - buy_price) / buy_price
                        break
                    
                    if hold_day == max_hold_days - 1:
                        if sold_half:
                            total_return += 0.5 * (close[check_idx] - buy_price) / buy_price
                        else:
                            total_return = (close[check_idx] - buy_price) / buy_price
                
                all_trades.append({'return': total_return})
    
    return all_trades


def run_backtest_strategy7(data, start_date, end_date, position_per_stock=0.02, max_total_position=0.80,
                           max_hold_days=10):
    """策略7: 动态止盈 - 根据持仓天数调整止盈比例"""
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        hist = calc_macd(close)
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
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if hold_day < 3:
                        take_profit_pct = 0.03
                    elif hold_day < 5:
                        take_profit_pct = 0.025
                    elif hold_day < 7:
                        take_profit_pct = 0.02
                    else:
                        take_profit_pct = 0.015
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'return': ret})
    
    return all_trades


def calculate_metrics(trades):
    if not trades:
        return {'totalReturn': 0, 'winRate': 0, 'profitFactor': 0, 'trades': 0, 'avgReturn': 0}
    
    returns = [t['return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    total_return = sum(returns)
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    
    total_profit = sum(wins)
    total_loss = abs(sum(losses))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    avg_return = np.mean(returns) * 100 if returns else 0
    
    return {
        'totalReturn': total_return * 100,
        'winRate': win_rate,
        'profitFactor': profit_factor,
        'trades': len(trades),
        'avgReturn': avg_return
    }


def main():
    print("=" * 70)
    print("卖点策略对比测试 - 7种不同卖点")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("\n运行7种卖点策略...")
    
    strategies = [
        ("策略1: 原策略(止盈3%,持仓10天)", run_backtest_strategy1, {}),
        ("策略2: 缩短持仓(止盈3%,持仓5天)", run_backtest_strategy2, {'max_hold_days': 5}),
        ("策略3: 添加止损(止盈3%,止损5%)", run_backtest_strategy3, {'stop_loss_pct': 0.05}),
        ("策略4: 移动止盈(止盈3%,回撤2%)", run_backtest_strategy4, {'trailing_pct': 0.02}),
        ("策略5: 时间止损(3天没涨2%就卖)", run_backtest_strategy5, {'time_stop_days': 3}),
        ("策略6: 分批止盈(2%卖一半,5%清仓)", run_backtest_strategy6, {}),
        ("策略7: 动态止盈(随时间降低止盈)", run_backtest_strategy7, {}),
    ]
    
    print(f"\n{'策略':^35} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-" * 85)
    
    results = []
    for name, func, kwargs in strategies:
        trades = func(data, start_date, end_date, **kwargs)
        metrics = calculate_metrics(trades)
        results.append((name, metrics))
        
        print(f"{name:^35} {metrics['trades']:^8} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['totalReturn']:^10.1f} {metrics['avgReturn']:^10.2f}")
    
    print("\n" + "=" * 70)
    print("策略排名（按总收益）")
    print("=" * 70)
    
    sorted_results = sorted(results, key=lambda x: x[1]['totalReturn'], reverse=True)
    
    for i, (name, metrics) in enumerate(sorted_results, 1):
        print(f"\n第{i}名: {name}")
        print(f"  总收益: {metrics['totalReturn']:.1f}%")
        print(f"  胜率: {metrics['winRate']:.1f}%")
        print(f"  盈亏比: {metrics['profitFactor']:.2f}")
        print(f"  交易数: {metrics['trades']}")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    best = sorted_results[0]
    print(f"\n最优策略: {best[0]}")
    print(f"相比原策略提升: {best[1]['totalReturn'] - results[0][1]['totalReturn']:.1f}%")


if __name__ == "__main__":
    main()
