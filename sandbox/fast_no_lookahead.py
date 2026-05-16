"""
快速防未来函数回测 - 针对MACD四阴线策略

策略：
1. 一次性计算所有股票的MACD信号（使用昨日收盘价）
2. 过滤条件也一次性计算
3. 按日期执行交易（次日开盘买入）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from collections import defaultdict


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


def calc_std(close: np.ndarray, period: int) -> np.ndarray:
    std = np.zeros(len(close))
    for i in range(period - 1, len(close)):
        std[i] = np.std(close[i - period + 1:i + 1])
    return std


def detect_macd_signal(histogram: np.ndarray) -> np.ndarray:
    """检测MACD四阴线信号"""
    n = len(histogram)
    signals = np.zeros(n, dtype=bool)
    for i in range(4, n):
        b0, b1, b2, b3 = histogram[i-3], histogram[i-2], histogram[i-1], histogram[i]
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


def fast_no_lookahead_backtest(daily_data, config, start_date, end_date):
    """快速防未来函数回测"""
    
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
    all_signal_dates = defaultdict(list)
    
    for sc, d in daily_data.items():
        dates = d['dates']
        close = np.asarray(d['close'], dtype=np.float64)
        open_prices = np.asarray(d['open'], dtype=np.float64)
        high = np.asarray(d['high'], dtype=np.float64)
        low = np.asarray(d['low'], dtype=np.float64)
        volume = np.asarray(d['volume'], dtype=np.float64)
        
        if len(close) < 50:
            continue
        
        dates_str = np.array([str(x)[:10] for x in dates])
        
        # 计算指标
        ma5 = calc_ma(close, 5)
        ma10 = calc_ma(close, 10)
        histogram = calc_macd(close)
        rsi_val = calc_rsi(close)
        
        # 检测MACD信号
        signals = detect_macd_signal(histogram)
        
        for i in range(len(signals)):
            if not signals[i]:
                continue
            
            signal_date = dates_str[i]
            if signal_date < start_date or signal_date > end_date:
                continue
            
            # 买入日期：信号日后一天
            if i + 1 >= len(close):
                continue
            
            buy_price = open_prices[i + 1]
            if buy_price <= 0:
                continue
            
            # 过滤条件（使用信号日收盘数据，无未来函数）
            vs = calc_volatility_strength(close, high, low, i)
            if vs < vs_threshold:
                continue
            
            if rsi_filter and rsi_val[i] >= rsi_max:
                continue
            
            if ma_diff_filter and ma10[i] > 0:
                ma_diff = (ma5[i] - ma10[i]) / ma10[i]
                if ma_diff < ma_diff_threshold:
                    continue
            
            all_signal_dates[signal_date].append({
                'stock_code': sc,
                'buy_date': dates_str[i + 1],
                'buy_price': buy_price,
                'vs': vs,
            })
    
    # 按日期执行交易
    initial_capital = 100000.0
    capital = initial_capital
    holdings = {}
    equity_curve = []
    
    all_dates = sorted(all_signal_dates.keys())
    
    for date in all_dates:
        # 卖出持仓
        for sc in list(holdings.keys()):
            h = holdings[sc]
            if h['sell_date'] == date:
                capital += h['position_value'] * (1 + h['return'])
                del holdings[sc]
        
        # 买入新信号
        signals = all_signal_dates[date]
        for sig in signals:
            if sig['stock_code'] in holdings:
                continue
            if len(holdings) < 5:
                position_value = initial_capital * 0.18
                capital -= position_value
                
                # 模拟卖出
                buy_price = sig['buy_price']
                highest_price = buy_price
                sell_price = buy_price
                sell_reason = 'max_days'
                hold_days = 0
                
                # 找到对应股票的后续数据
                sc = sig['stock_code']
                d = daily_data.get(sc)
                if d is None:
                    continue
                
                dates_str = np.array([str(x)[:10] for x in d['dates']])
                close = np.asarray(d['close'], dtype=np.float64)
                high = np.asarray(d['high'], dtype=np.float64)
                
                # 找到买入日在数组中的位置
                try:
                    buy_idx = list(dates_str).index(sig['buy_date'])
                except:
                    continue
                
                for day in range(max_hold_days):
                    chk = buy_idx + day + 1
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
                
                ret = (sell_price - buy_price) / buy_price
                
                holdings[sc] = {
                    'position_value': position_value,
                    'return': ret,
                    'sell_date': sell_date,
                }
        
        # 记录权益
        equity = capital + sum(h['position_value'] * (1 + h['return']) for h in holdings.values())
        equity_curve.append({'date': date, 'equity': equity})
    
    # 最终清仓
    for sc in holdings:
        capital += holdings[sc]['position_value'] * (1 + holdings[sc]['return'])
    
    # 计算结果
    total_return = (capital - initial_capital) / initial_capital * 100
    
    equity_arr = np.array([e['equity'] for e in equity_curve])
    if len(equity_arr) > 0:
        cummax = np.maximum.accumulate(equity_arr)
        drawdown = (cummax - equity_arr) / cummax
        max_drawdown = np.max(drawdown) * 100
    else:
        max_drawdown = 0
    
    trade_count = sum(len(all_signal_dates[d]) for d in all_signal_dates)
    
    return {
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'trade_count': trade_count,
        'equity_curve': equity_curve,
    }


if __name__ == "__main__":
    import time
    from sandbox.top3_backtest import load_data
    
    t0 = time.time()
    daily_data = load_data('2024-01-01', '2024-12-31')
    print(f"数据加载: {time.time()-t0:.1f}s")
    
    config = {
        'vs_threshold': 0.0,
        'rsi_filter': False,
        'volume_filter': False,
        'take_profit_pct': 0.05,
        'stop_loss_pct': 0.02,
        'trailing_stop_pct': 0.02,
        'max_holding_days': 10,
    }
    
    t0 = time.time()
    result = fast_no_lookahead_backtest(daily_data, config, '2024-01-01', '2024-12-31')
    print(f"回测时间: {time.time()-t0:.1f}s")
    print(f"交易次数: {result['trade_count']}")
    print(f"总收益: {result['total_return']:.1f}%")
    print(f"最大回撤: {result['max_drawdown']:.1f}%")
