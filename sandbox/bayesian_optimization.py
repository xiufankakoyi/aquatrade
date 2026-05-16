"""
MACD 四阴线策略 - 阶段2：贝叶斯优化

使用 Optuna 进行贝叶斯优化，找出最优参数组合
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
import json


def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
    return ema


def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return histogram


def calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
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
            rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    rsi[:period] = 50
    return rsi


def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    atr = np.zeros(n)
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr


def calc_ma(close: np.ndarray, period: int) -> np.ndarray:
    ma = np.zeros(len(close))
    for i in range(period - 1, len(close)):
        ma[i] = np.mean(close[i - period + 1:i + 1])
    return ma


def calc_vol_ma(volume: np.ndarray, period: int = 5) -> np.ndarray:
    ma = np.zeros(len(volume))
    for i in range(period - 1, len(volume)):
        ma[i] = np.mean(volume[i - period + 1:i + 1])
    return ma


def calc_std(close: np.ndarray, period: int) -> np.ndarray:
    std = np.zeros(len(close))
    for i in range(period - 1, len(close)):
        std[i] = np.std(close[i - period + 1:i + 1])
    return std


def detect_signal(bars: np.ndarray) -> np.ndarray:
    n = len(bars)
    signals = np.zeros(n, dtype=bool)
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                signals[i] = True
    return signals


def calc_volatility_strength(close: np.ndarray, high: np.ndarray, low: np.ndarray, idx: int) -> float:
    if idx < 20 or idx >= len(close):
        return 0.0
    atr = calc_atr(high, low, close)
    std20 = calc_std(close, 20)
    atr_pct = atr[idx] / close[idx] * 100 if close[idx] > 0 else 0
    high_low_range = (high[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    std20_pct = std20[idx] / close[idx] * 100 if close[idx] > 0 else 0
    lower_shadow = (close[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    return 0.35 * (atr_pct - 3.0) / 1.5 + 0.30 * (high_low_range - 2.5) / 1.5 + 0.20 * (std20_pct - 3.5) / 1.5 + 0.15 * (lower_shadow - 1.5) / 1.5


def load_data(start_date: str, end_date: str):
    from sandbox.top3_backtest_fixed import load_data as ld
    return ld(start_date, end_date)


def run_backtest(daily_data, config):
    """运行回测"""
    from collections import defaultdict
    
    all_trades = []
    start_date = config['start_date']
    end_date = config['end_date']
    
    vs_threshold = config.get('vs_threshold', 0)
    rsi_filter = config.get('rsi_filter', False)
    rsi_max = config.get('rsi_max', 60)
    ma_diff_filter = config.get('ma_diff_filter', False)
    ma_diff_threshold = config.get('ma_diff_threshold', 0)
    
    take_profit = config.get('take_profit_pct', 0.03)
    stop_loss = config.get('stop_loss_pct', 0.02)
    trailing_stop = config.get('trailing_stop_pct', 0.02)
    max_hold_days = config.get('max_holding_days', 10)
    
    for sc, d in daily_data.items():
        dates = d['dates']
        close = d['close'].astype(np.float64)
        open_prices = d['open'].astype(np.float64)
        high = d['high'].astype(np.float64)
        low = d['low'].astype(np.float64)
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 50:
            continue
        
        dates_str = np.array([str(d)[:10] for d in dates])
        mask = (dates_str >= start_date) & (dates_str <= end_date)
        if not np.any(mask):
            continue
        
        histogram = calc_macd(close)
        rsi = calc_rsi(close)
        ma5 = calc_ma(close, 5)
        ma10 = calc_ma(close, 10)
        vol_ma5 = calc_vol_ma(volume, 5)
        
        signals = detect_signal(histogram)
        
        for i in range(len(signals) - 1):
            if not signals[i]:
                continue
            
            if dates_str[i] < start_date or dates_str[i] > end_date:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close):
                continue
            
            # 买入条件过滤
            vs = calc_volatility_strength(close, high, low, i)
            if vs < vs_threshold:
                continue
            
            if rsi_filter and rsi[i] >= rsi_max:
                continue
            
            if ma_diff_filter:
                if ma10[i] <= 0:
                    continue
                ma_diff = (ma5[i] - ma10[i]) / ma10[i]
                if ma_diff < ma_diff_threshold:
                    continue
            
            buy_price = open_prices[buy_idx]
            entry_date = dates_str[buy_idx]
            
            highest_price = buy_price
            sell_price = buy_price
            sell_date = entry_date
            hold_days = 0
            sell_reason = ''
            
            for day in range(max_hold_days):
                chk = buy_idx + day
                if chk >= len(close):
                    sell_price = close[-1]
                    sell_date = dates_str[-1]
                    hold_days = day
                    sell_reason = 'max_days'
                    break
                
                current_price = close[chk]
                if high[chk] > highest_price:
                    highest_price = high[chk]
                
                ret = (current_price - buy_price) / buy_price
                
                if ret >= take_profit:
                    sell_price = current_price
                    sell_date = dates_str[chk]
                    hold_days = day + 1
                    sell_reason = 'take_profit'
                    break
                
                if ret <= -stop_loss:
                    sell_price = current_price
                    sell_date = dates_str[chk]
                    hold_days = day + 1
                    sell_reason = 'stop_loss'
                    break
                
                if highest_price > buy_price * 1.03:
                    if (highest_price - current_price) / highest_price >= trailing_stop:
                        sell_price = current_price
                        sell_date = dates_str[chk]
                        hold_days = day + 1
                        sell_reason = 'trailing_stop'
                        break
                
                sell_price = current_price
                sell_date = dates_str[chk]
                hold_days = day + 1
            
            ret = (sell_price - buy_price) / buy_price
            
            all_trades.append({
                'stock_code': sc,
                'buy_date': entry_date,
                'sell_date': sell_date,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'return': ret,
                'hold_days': hold_days,
                'sell_reason': sell_reason,
            })
    
    # 计算收益
    if not all_trades:
        return {
            'total_return': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'win_rate': 0,
            'trade_count': 0,
        }
    
    initial_capital = 100000.0
    capital = initial_capital
    holdings = {}
    equity_curve = []
    
    trades_by_buy = defaultdict(list)
    for t in all_trades:
        trades_by_buy[t['buy_date']].append(t)
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    for date in all_dates:
        for sc in list(holdings.keys()):
            h = holdings[sc]
            if h['sell_date'] == date:
                capital += h['position_value'] * (1 + h['return'])
                del holdings[sc]
        
        if date in trades_by_buy:
            for t in trades_by_buy[date]:
                if t['stock_code'] in holdings:
                    continue
                if len(holdings) < 5:
                    position_value = initial_capital * 0.18
                    capital -= position_value
                    holdings[t['stock_code']] = {
                        'position_value': position_value,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                    }
        
        equity = capital + sum(h['position_value'] * (1 + h['return']) for h in holdings.values())
        equity_curve.append(equity)
    
    for sc in holdings:
        capital += holdings[sc]['position_value'] * (1 + holdings[sc]['return'])
    
    total_return = (capital - initial_capital) / initial_capital * 100
    
    # 计算最大回撤
    equity_arr = np.array(equity_curve)
    cummax = np.maximum.accumulate(equity_arr)
    drawdown = (cummax - equity_arr) / cummax
    max_drawdown = np.max(drawdown) * 100
    
    # 计算夏普比率
    if len(equity_curve) > 1:
        returns = np.diff(equity_curve) / equity_arr[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0
    
    # 胜率
    wins = sum(1 for t in all_trades if t['return'] > 0)
    win_rate = wins / len(all_trades) * 100 if all_trades else 0
    
    return {
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'win_rate': win_rate,
        'trade_count': len(all_trades),
    }


def objective(trial, daily_data, test_start, test_end):
    """Optuna 目标函数"""
    
    # 放宽参数范围以增加信号数量
    config = {
        'start_date': test_start,
        'end_date': test_end,
        
        # 买入条件 - 放宽范围
        'vs_threshold': trial.suggest_float('vs_threshold', 0, 0.8),
        'rsi_filter': trial.suggest_categorical('rsi_filter', [True, False]),
        'rsi_max': trial.suggest_float('rsi_max', 35, 70),
        'ma_diff_filter': trial.suggest_categorical('ma_diff_filter', [True, False]),
        'ma_diff_threshold': trial.suggest_float('ma_diff_threshold', 0, 0.1),
        
        # 卖出条件
        'take_profit_pct': trial.suggest_float('take_profit_pct', 0.01, 0.10),
        'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.01, 0.05),
        'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.01, 0.05),
        'max_holding_days': trial.suggest_int('max_holding_days', 5, 20),
    }
    
    result = run_backtest(daily_data, config)
    
    # 约束：每年至少 100 笔交易
    years = (pd.to_datetime(test_end) - pd.to_datetime(test_start)).days / 365
    min_trades_per_year = 100
    required_trades = int(min_trades_per_year * years)
    
    trade_count = result['trade_count']
    
    # 如果交易次数不足，施加惩罚
    if trade_count < required_trades:
        # 使用交易次数不足的比例作为惩罚
        penalty = (trade_count / required_trades) * 0.5  # 最多扣 0.5
        return max(result['sharpe_ratio'] - penalty, -1.0)
    
    # 优化目标：夏普比率
    return result['sharpe_ratio']


def main():
    print("=" * 60)
    print("MACD四阴线策略 - 阶段2：贝叶斯优化")
    print("=" * 60)
    
    # 加载数据
    train_start = "2024-01-01"
    train_end = "2024-12-31"
    test_start = "2025-01-01"
    test_end = "2025-12-31"
    
    print("\n加载数据...")
    daily_data = load_data(train_start, test_end)
    
    print(f"\n训练期: {train_start} ~ {train_end}")
    print(f"测试期: {test_start} ~ {test_end}")
    
    # 先在训练集上优化
    print("\n开始贝叶斯优化...")
    
    study = optuna.create_study(
        direction='maximize',
        sampler=TPESampler(seed=42)
    )
    
    study.optimize(
        lambda trial: objective(trial, daily_data, train_start, train_end),
        n_trials=50,
        show_progress_bar=True
    )
    
    print(f"\n最佳试验:")
    print(f"  夏普比率: {study.best_value:.3f}")
    print(f"  参数: {study.best_params}")
    
    # 在测试集上验证
    print("\n在测试集上验证...")
    best_config = {
        'start_date': test_start,
        'end_date': test_end,
        **study.best_params
    }
    
    test_result = run_backtest(daily_data, best_config)
    
    print(f"\n测试集结果:")
    print(f"  总收益: {test_result['total_return']:.2f}%")
    print(f"  最大回撤: {test_result['max_drawdown']:.2f}%")
    print(f"  夏普比率: {test_result['sharpe_ratio']:.3f}")
    print(f"  胜率: {test_result['win_rate']:.1f}%")
    print(f"  交易次数: {test_result['trade_count']}")
    
    # 保存结果
    result = {
        'best_params': study.best_params,
        'train_sharpe': study.best_value,
        'test_result': test_result,
    }
    
    output_path = Path(__file__).parent / "bayesian_optimization_results.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
