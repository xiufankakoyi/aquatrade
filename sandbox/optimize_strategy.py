"""
策略优化测试
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
def detect_signal(bars: np.ndarray, threshold: float = -0.005) -> np.ndarray:
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3):
                if b3 > threshold:
                    signals[i] = True
    
    return signals


def run_backtest(data: PreloadedData, start_date: str, end_date: str,
                 position_per_stock: float = 0.02, max_total_position: float = 0.80,
                 take_profit_pct: float = 0.03, max_hold_days: int = 10,
                 macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 threshold: float = -0.005):
    """运行回测"""
    
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
        
        hist = calc_macd(close, macd_fast, macd_slow, macd_signal)
        signals = detect_signal(hist, threshold)
        
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
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret
                })
    
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
    equity_curve = []
    trades_log = []
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                trades_log.append(h['return'])
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if current_position_pct + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position_pct += position_per_stock
        
        equity_curve.append(capital)
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
        trades_log.append(h['return'])
    
    return capital, trades_log, len(all_trades)


def calculate_metrics(final_capital: float, trades_log: list, equity_curve: list):
    """计算策略指标"""
    total_return = (final_capital - 100000) / 100000 * 100
    
    if not trades_log:
        return {'totalReturn': 0, 'winRate': 0, 'profitFactor': 0, 'trades': 0, 'sharpeRatio': 0, 'maxDrawdown': 0}
    
    wins = [r for r in trades_log if r > 0]
    losses = [r for r in trades_log if r < 0]
    win_rate = len(wins) / len(trades_log) * 100
    
    total_profit = sum(wins)
    total_loss = abs(sum(losses))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    equity_values = [100000] + equity_curve
    peak = equity_values[0]
    max_dd = 0
    for eq in equity_values:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    max_drawdown = max_dd * 100
    
    returns = []
    for i in range(1, len(equity_values)):
        ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
        returns.append(ret)
    
    if len(returns) > 1 and np.std(returns) > 0:
        rf = 0.02 / 252
        excess_returns = np.array(returns) - rf
        sharpe = np.mean(excess_returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe = 0
    
    return {
        'totalReturn': total_return,
        'winRate': win_rate,
        'profitFactor': profit_factor,
        'trades': len(trades_log),
        'sharpeRatio': sharpe,
        'maxDrawdown': max_drawdown
    }


def main():
    print("=" * 70)
    print("策略参数优化测试")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("\n" + "=" * 70)
    print("测试1: 止盈比例优化")
    print("=" * 70)
    
    tp_tests = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
    
    print(f"\n{'止盈%':^8} {'收益%':^10} {'胜率%':^8} {'盈亏比':^8} {'夏普':^8} {'回撤%':^8} {'交易数':^8}")
    print("-" * 65)
    
    for tp in tp_tests:
        final_cap, trades_log, signals = run_backtest(
            data, start_date, end_date,
            position_per_stock=0.02, max_total_position=0.80,
            take_profit_pct=tp, max_hold_days=10
        )
        equity_curve = []
        metrics = calculate_metrics(final_cap, trades_log, equity_curve)
        print(f"{tp*100:^8.0f} {metrics['totalReturn']:^10.1f} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['sharpeRatio']:^8.2f} {metrics['maxDrawdown']:^8.1f} {metrics['trades']:^8}")
    
    print("\n" + "=" * 70)
    print("测试2: 最大持仓天数优化")
    print("=" * 70)
    
    hold_days_tests = [3, 5, 7, 10, 15, 20, 30]
    
    print(f"\n{'持仓天数':^10} {'收益%':^10} {'胜率%':^8} {'盈亏比':^8} {'夏普':^8} {'回撤%':^8} {'交易数':^8}")
    print("-" * 65)
    
    for hd in hold_days_tests:
        final_cap, trades_log, signals = run_backtest(
            data, start_date, end_date,
            position_per_stock=0.02, max_total_position=0.80,
            take_profit_pct=0.03, max_hold_days=hd
        )
        equity_curve = []
        metrics = calculate_metrics(final_cap, trades_log, equity_curve)
        print(f"{hd:^10} {metrics['totalReturn']:^10.1f} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['sharpeRatio']:^8.2f} {metrics['maxDrawdown']:^8.1f} {metrics['trades']:^8}")
    
    print("\n" + "=" * 70)
    print("测试3: 仓位优化")
    print("=" * 70)
    
    position_tests = [
        (0.01, 0.50), (0.01, 0.80),
        (0.02, 0.50), (0.02, 0.80),
        (0.03, 0.80), (0.05, 0.80),
        (0.10, 0.80), (0.10, 1.00),
    ]
    
    print(f"\n{'单股%':^8} {'总仓%':^8} {'收益%':^10} {'胜率%':^8} {'盈亏比':^8} {'夏普':^8} {'交易数':^8}")
    print("-" * 60)
    
    for pos, max_pos in position_tests:
        final_cap, trades_log, signals = run_backtest(
            data, start_date, end_date,
            position_per_stock=pos, max_total_position=max_pos,
            take_profit_pct=0.03, max_hold_days=10
        )
        equity_curve = []
        metrics = calculate_metrics(final_cap, trades_log, equity_curve)
        print(f"{pos*100:^8.0f} {max_pos*100:^8.0f} {metrics['totalReturn']:^10.1f} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['sharpeRatio']:^8.2f} {metrics['trades']:^8}")
    
    print("\n" + "=" * 70)
    print("测试4: 绿柱阈值优化")
    print("=" * 70)
    
    threshold_tests = [-0.01, -0.005, -0.003, -0.001, 0.0]
    
    print(f"\n{'阈值':^10} {'收益%':^10} {'胜率%':^8} {'盈亏比':^8} {'夏普':^8} {'信号数':^8}")
    print("-" * 60)
    
    for th in threshold_tests:
        final_cap, trades_log, signals = run_backtest(
            data, start_date, end_date,
            position_per_stock=0.02, max_total_position=0.80,
            take_profit_pct=0.03, max_hold_days=10,
            threshold=th
        )
        equity_curve = []
        metrics = calculate_metrics(final_cap, trades_log, equity_curve)
        print(f"{th:^10.4f} {metrics['totalReturn']:^10.1f} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['sharpeRatio']:^8.2f} {signals:^8}")
    
    print("\n" + "=" * 70)
    print("测试5: 最优参数组合")
    print("=" * 70)
    
    best_combinations = [
        {'name': '保守型', 'tp': 0.03, 'hold': 10, 'pos': 0.02, 'max_pos': 0.80},
        {'name': '稳健型', 'tp': 0.04, 'hold': 15, 'pos': 0.03, 'max_pos': 0.80},
        {'name': '激进型', 'tp': 0.05, 'hold': 20, 'pos': 0.05, 'max_pos': 0.80},
        {'name': '高频型', 'tp': 0.02, 'hold': 5, 'pos': 0.02, 'max_pos': 0.80},
    ]
    
    print(f"\n{'策略名':^10} {'止盈%':^8} {'持仓':^6} {'单股%':^6} {'总仓%':^6} {'收益%':^10} {'夏普':^8}")
    print("-" * 65)
    
    for combo in best_combinations:
        final_cap, trades_log, signals = run_backtest(
            data, start_date, end_date,
            position_per_stock=combo['pos'], max_total_position=combo['max_pos'],
            take_profit_pct=combo['tp'], max_hold_days=combo['hold']
        )
        equity_curve = []
        metrics = calculate_metrics(final_cap, trades_log, equity_curve)
        print(f"{combo['name']:^10} {combo['tp']*100:^8.0f} {combo['hold']:^6} {combo['pos']*100:^6.0f} {combo['max_pos']*100:^6.0f} {metrics['totalReturn']:^10.1f} {metrics['sharpeRatio']:^8.2f}")
    
    print("\n" + "=" * 70)
    print("优化测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
