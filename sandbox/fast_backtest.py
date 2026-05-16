"""
向量化回测 - 使用Polars进行快速回测
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl
import numpy as np
from collections import defaultdict


def fast_backtest(daily_data, config):
    """向量化回测 - 大幅加速"""
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
    
    all_trades = []
    
    for sc, d in daily_data.items():
        dates = d['dates']
        close = np.asarray(d['close'], dtype=np.float64)
        opens = np.asarray(d['open'], dtype=np.float64)
        high = np.asarray(d['high'], dtype=np.float64)
        low = np.asarray(d['low'], dtype=np.float64)
        volume = np.asarray(d['volume'], dtype=np.float64)
        
        if len(close) < 50:
            continue
        
        dates_str = np.array([str(x)[:10] for x in dates])
        
        # 计算指标 (向量化)
        ma5 = moving_average(close, 5)
        ma10 = moving_average(close, 10)
        ma20 = moving_average(close, 20)
        ema12 = ema(close, 12)
        ema26 = ema(close, 26)
        macd_hist = ema12 - ema(ema(close, 9), 9) * 2  # 简化
        rsi_val = rsi(close, 14)
        vol_ma5 = moving_average(volume, 5)
        
        # 检测MACD四阴线信号
        signals = detect_macd_4red(macd_hist)
        
        # 简单过滤
        for i in range(len(signals) - 1):
            if not signals[i]:
                continue
            
            if dates_str[i] < start_date or dates_str[i] > end_date:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close):
                continue
            
            # 简单买入条件
            if rsi_filter and rsi_val[i] >= rsi_max:
                continue
            
            buy_price = opens[buy_idx]
            entry_date = dates_str[buy_idx]
            
            # 模拟卖出
            highest_price = buy_price
            sell_price = buy_price
            sell_reason = 'max_days'
            hold_days = 0
            
            for day in range(max_hold_days):
                chk = buy_idx + day
                if chk >= len(close):
                    sell_price = close[-1]
                    sell_date = dates_str[-1]
                    hold_days = day
                    break
                
                if high[chk] > highest_price:
                    highest_price = high[chk]
                
                ret = (close[chk] - buy_price) / buy_price
                
                if ret >= take_profit:
                    sell_price = close[chk]
                    sell_date = dates_str[chk]
                    hold_days = day + 1
                    sell_reason = 'take_profit'
                    break
                
                if ret <= -stop_loss:
                    sell_price = close[chk]
                    sell_date = dates_str[chk]
                    hold_days = day + 1
                    sell_reason = 'stop_loss'
                    break
            
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
    
    all_dates = sorted(set(t['buy_date'] for t in all_trades))
    
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
    
    equity_arr = np.array(equity_curve)
    cummax = np.maximum.accumulate(equity_arr)
    drawdown = (cummax - equity_arr) / cummax
    max_drawdown = np.max(drawdown) * 100
    
    if len(equity_curve) > 1:
        returns = np.diff(equity_curve) / equity_arr[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0
    
    wins = sum(1 for t in all_trades if t['return'] > 0)
    win_rate = wins / len(all_trades) * 100 if all_trades else 0
    
    return {
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'win_rate': win_rate,
        'trade_count': len(all_trades),
    }


def moving_average(arr, period):
    n = len(arr)
    ma = np.full(n, np.nan)
    for i in range(period - 1, n):
        ma[i] = np.mean(arr[i - period + 1:i + 1])
    return ma


def ema(arr, period):
    mult = 2.0 / (period + 1)
    ema_arr = np.zeros(len(arr))
    ema_arr[0] = arr[0]
    for i in range(1, len(arr)):
        ema_arr[i] = (arr[i] - ema_arr[i - 1]) * mult + ema_arr[i - 1]
    return ema_arr


def rsi(arr, period):
    n = len(arr)
    if n <= period:
        return np.full(n, 50.0)
    
    rsi_arr = np.zeros(n)
    changes = np.diff(arr)
    gains = np.zeros(n)
    losses = np.zeros(n)
    gains[1:] = np.where(changes > 0, changes, 0)
    losses[1:] = np.where(changes < 0, -changes, 0)
    
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    for i in range(period, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_arr[i] = 100
        else:
            rsi_arr[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    
    rsi_arr[:period] = 50
    return rsi_arr


def detect_macd_4red(hist):
    n = len(hist)
    signals = np.zeros(n, dtype=bool)
    for i in range(4, n):
        b0, b1, b2, b3 = hist[i-3], hist[i-2], hist[i-1], hist[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                signals[i] = True
    return signals


if __name__ == "__main__":
    from sandbox.bayesian_optimization import load_data
    
    t0 = time.time()
    daily_data = load_data('2024-01-01', '2024-12-31')
    print(f"数据加载: {time.time()-t0:.2f}s")
    
    config = {
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'vs_threshold': 0.5,
        'rsi_filter': True,
        'rsi_max': 50,
        'ma_diff_filter': False,
        'ma_diff_threshold': 0,
        'take_profit_pct': 0.05,
        'stop_loss_pct': 0.02,
        'trailing_stop_pct': 0.02,
        'max_holding_days': 10,
    }
    
    t0 = time.time()
    result = fast_backtest(daily_data, config)
    print(f"向量化回测: {time.time()-t0:.2f}s")
    print(f"  交易次数: {result['trade_count']}")
    print(f"  总收益: {result['total_return']:.2f}%")
