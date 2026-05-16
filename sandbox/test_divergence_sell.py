"""
技术指标背离卖点策略测试

测试卖点：
1. MACD顶背离 - 股价创新高，MACD红柱/DIF高点降低
2. RSI顶背离 - 股价创新高，RSI高点降低
3. 量价背离 - 股价创新高，成交量萎缩
4. 均线乖离过大 - 股价偏离60日均线超过一定比例
5. 布林带出轨 - 股价冲出布林带上轨
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
from numba import njit
from collections import defaultdict
from datetime import datetime

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


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
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    rsi[:period] = 50
    return rsi


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


@njit
def find_local_peaks(arr: np.ndarray, window: int = 5) -> np.ndarray:
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


def load_factor_data(stock_code: str, start_date: str, end_date: str) -> dict:
    """从ArcticDB加载因子数据"""
    try:
        arctic = get_arctic_instance_for_library('factor')
        if arctic is None:
            return None
        
        lib = arctic['factor']
        symbol = f"momentum_{stock_code}"
        
        if symbol not in lib.list_symbols():
            return None
        
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        df = df.reset_index()
        
        if 'trade_date' in df.columns:
            if df['trade_date'].dtype == 'datetime64[ns]':
                df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d')
            else:
                df['trade_date'] = df['trade_date'].astype(str)
            
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
        
        result = {'dates': df['trade_date'].values}
        for col in df.columns:
            if col != 'trade_date':
                result[col] = df[col].values
        
        return result
    
    except Exception as e:
        return None


def load_daily_data(start_date: str, end_date: str) -> dict:
    """加载日线数据"""
    import lancedb
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_df = daily_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    data = {}
    for row in daily_df.iter_rows(named=True):
        stock_code = row['stock_code']
        if stock_code not in data:
            data[stock_code] = {
                'dates': [],
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
            }
        data[stock_code]['dates'].append(str(row['trade_date']))
        data[stock_code]['open'].append(row.get('open', row.get('close')))
        data[stock_code]['high'].append(row.get('high', row.get('close')))
        data[stock_code]['low'].append(row.get('low', row.get('close')))
        data[stock_code]['close'].append(row['close'])
        data[stock_code]['volume'].append(row['volume'])
    
    for stock_code in data:
        dates_arr = np.array(data[stock_code]['dates'])
        sorted_idx = np.argsort(dates_arr)
        
        for key in ['dates', 'open', 'high', 'low', 'close', 'volume']:
            arr = np.array(data[stock_code][key])
            data[stock_code][key] = arr[sorted_idx]
    
    return data


def run_strategy_macd_divergence(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03):
    """策略1: MACD顶背离卖点"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        peaks = find_local_peaks(close, window=5)
        hist_peaks = find_local_peaks(hist, window=5)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if peaks[check_idx]:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0:
                            if close[check_idx] > close[prev_peak_idx]:
                                if hist[check_idx] < hist[prev_peak_idx]:
                                    sell_price = close[check_idx]
                                    sold = True
                                    break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_rsi_divergence(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03):
    """策略2: RSI顶背离卖点"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        rsi_peaks = find_local_peaks(rsi, window=5)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if peaks[check_idx] and rsi[check_idx] > 70:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j] and rsi[j] > 60:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0:
                            if close[check_idx] > close[prev_peak_idx]:
                                if rsi[check_idx] < rsi[prev_peak_idx]:
                                    sell_price = close[check_idx]
                                    sold = True
                                    break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_volume_divergence(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03):
    """策略3: 量价背离卖点"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 50:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        peaks = find_local_peaks(close, window=5)
        vol_peaks = find_local_peaks(volume, window=5)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if peaks[check_idx]:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0:
                            if close[check_idx] > close[prev_peak_idx]:
                                if volume[check_idx] < volume[prev_peak_idx] * 0.7:
                                    sell_price = close[check_idx]
                                    sold = True
                                    break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_ma_deviation(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03, deviation_threshold=0.15):
    """策略4: 均线乖离过大卖点"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        
        if len(close) < 70:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        ma60 = np.zeros(len(close))
        for i in range(60, len(close)):
            ma60[i] = np.mean(close[i-60:i])
        ma60[:60] = close[:60]
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if ma60[check_idx] > 0:
                        deviation = (close[check_idx] - ma60[check_idx]) / ma60[check_idx]
                        if deviation >= deviation_threshold:
                            sell_price = close[check_idx]
                            sold = True
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_boll_breakout(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03):
    """策略5: 布林带出轨卖点"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        boll_mid = np.zeros(len(close))
        boll_upper = np.zeros(len(close))
        boll_std = np.zeros(len(close))
        
        for i in range(20, len(close)):
            boll_mid[i] = np.mean(close[i-20:i])
            boll_std[i] = np.std(close[i-20:i])
            boll_upper[i] = boll_mid[i] + 2 * boll_std[i]
        
        boll_mid[:20] = close[:20]
        boll_upper[:20] = close[:20]
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if close[check_idx] > boll_upper[check_idx]:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_combined_divergence(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03):
    """策略6: 组合背离卖点 (MACD+RSI+量价 任一触发)"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    divergence_triggered = False
                    
                    if peaks[check_idx]:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0 and close[check_idx] > close[prev_peak_idx]:
                            if hist[check_idx] < hist[prev_peak_idx]:
                                divergence_triggered = True
                            
                            if rsi[check_idx] < rsi[prev_peak_idx] and rsi[check_idx] > 70:
                                divergence_triggered = True
                            
                            if volume[check_idx] < volume[prev_peak_idx] * 0.7:
                                divergence_triggered = True
                    
                    if divergence_triggered:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
                    ret = (sell_price - buy_price) / buy_price
                    all_trades.append({'return': ret})
    
    return all_trades


def run_strategy_trailing_with_divergence(daily_data, start_date, end_date, max_hold_days=10, take_profit_pct=0.03, trailing_pct=0.02):
    """策略7: 移动止盈 + 背离信号组合"""
    all_trades = []
    
    for stock_code in daily_data:
        d = daily_data[stock_code]
        close = d['close']
        high = d['high']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        triggered_trailing = True
                    
                    divergence_sell = False
                    if peaks[check_idx]:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0 and close[check_idx] > close[prev_peak_idx]:
                            if hist[check_idx] < hist[prev_peak_idx]:
                                divergence_sell = True
                            if rsi[check_idx] < rsi[prev_peak_idx] and rsi[check_idx] > 75:
                                divergence_sell = True
                    
                    if divergence_sell and triggered_trailing:
                        sell_price = close[check_idx]
                        sold = True
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= trailing_pct:
                            sell_price = close[check_idx]
                            sold = True
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sold = True
                
                if sold:
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
    print("技术指标背离卖点策略测试")
    print("=" * 70)
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("\n加载数据...")
    daily_data = load_daily_data(start_date, end_date)
    print(f"加载了 {len(daily_data)} 只股票")
    
    print("\n运行技术指标背离卖点策略...")
    
    strategies = [
        ("策略1: MACD顶背离", run_strategy_macd_divergence, {}),
        ("策略2: RSI顶背离", run_strategy_rsi_divergence, {}),
        ("策略3: 量价背离", run_strategy_volume_divergence, {}),
        ("策略4: 均线乖离(15%)", run_strategy_ma_deviation, {'deviation_threshold': 0.15}),
        ("策略5: 布林带出轨", run_strategy_boll_breakout, {}),
        ("策略6: 组合背离(MACD+RSI+量价)", run_strategy_combined_divergence, {}),
        ("策略7: 移动止盈+背离", run_strategy_trailing_with_divergence, {}),
    ]
    
    print(f"\n{'策略':^35} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-" * 85)
    
    results = []
    for name, func, kwargs in strategies:
        trades = func(daily_data, start_date, end_date, **kwargs)
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


if __name__ == "__main__":
    main()
