"""
测试四个改进方向对策略的影响
1. 添加止损机制：买入后亏损超过5%强制止损
2. 大盘趋势过滤：当大盘MA20 < MA60时停止买入
3. 仓位管理：熊市降低总仓位
4. 提高买点质量：增加RSI超卖、成交量放大等过滤条件
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict

from data_cache import get_cache


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
def detect_signal_with_filter(bars: np.ndarray, rsi: np.ndarray, volume: np.ndarray, vol_ma: np.ndarray) -> np.ndarray:
    """带过滤条件的买点信号"""
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3):
                if b3 > -0.005:
                    if rsi[i] < 40:
                        if vol_ma[i] > 0 and volume[i] > vol_ma[i] * 1.2:
                            signals[i] = True
    return signals


def load_benchmark_data(start_date: str, end_date: str):
    """加载上证指数数据用于大盘趋势过滤"""
    try:
        from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
        arctic = get_arctic_instance_for_library('market_data')
        lib = arctic['market_data']
        item = lib.read('000001.SH', date_range=(pd.Timestamp(start_date), pd.Timestamp(end_date)))
        df = item.data.sort_index()
        
        close = df['close'].values
        dates = [idx.strftime('%Y-%m-%d') for idx in df.index]
        
        ma20 = np.zeros(len(close))
        ma60 = np.zeros(len(close))
        for i in range(20, len(close)):
            ma20[i] = np.mean(close[i-20:i])
        for i in range(60, len(close)):
            ma60[i] = np.mean(close[i-60:i])
        
        ma20[:20] = close[:20]
        ma60[:60] = close[:60]
        
        trend = {}
        for i, date in enumerate(dates):
            trend[date] = ma20[i] >= ma60[i]
        
        return trend
    except Exception as e:
        print(f"加载基准数据失败: {e}")
        return {}


def run_strategy(data, start_date, end_date, strategy_name, 
                 use_stop_loss=False, stop_loss_pct=0.05,
                 use_trend_filter=False, trend_data=None,
                 use_position_management=False,
                 use_quality_filter=False):
    """运行策略"""
    
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        low = d['low']
        volume = d['volume'].astype(np.float64)
        
        if len(close) < 70:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        low = low[mask]
        volume = volume[mask]
        dates = dates[mask]
        
        if len(close) < 70:
            continue
        
        _, _, hist = calc_macd(close)
        rsi = calc_rsi(close, period=14)
        
        vol_ma5 = np.zeros(len(volume))
        for i in range(5, len(volume)):
            vol_ma5[i] = np.mean(volume[i-5:i])
        vol_ma5[:5] = volume[:5]
        
        if use_quality_filter:
            signals = detect_signal_with_filter(hist, rsi, volume, vol_ma5)
        else:
            signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                
                if use_trend_filter and trend_data:
                    if buy_date in trend_data and not trend_data[buy_date]:
                        continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                max_hold_days = 10
                take_profit_pct = 0.03
                trailing_pct = 0.02
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    day_low_pct = (low[check_idx] - buy_price) / buy_price
                    
                    if use_stop_loss and day_low_pct <= -stop_loss_pct:
                        sell_price = close[check_idx]
                        break
                    
                    if day_high_pct >= take_profit_pct:
                        triggered_trailing = True
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= trailing_pct:
                            sell_price = close[check_idx]
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'return': ret,
                    'buy_date': buy_date,
                })
    
    return all_trades


def calculate_metrics(trades):
    if not trades:
        return {'totalReturn': 0, 'winRate': 0, 'profitFactor': 0, 'trades': 0, 'avgReturn': 0}
    
    returns = [t['return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    total_return = sum(returns) * 100
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
    avg_return = np.mean(returns) * 100 if returns else 0
    
    return {
        'totalReturn': total_return,
        'winRate': win_rate,
        'profitFactor': profit_factor,
        'trades': len(trades),
        'avgReturn': avg_return
    }


def main():
    print("=" * 70)
    print("测试四个改进方向")
    print("=" * 70)
    
    data = get_cache()
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("\n加载大盘趋势数据...")
    trend_data = load_benchmark_data(start_date, end_date)
    print(f"加载了 {len(trend_data)} 天的趋势数据")
    
    strategies = [
        ("原策略(基准)", {}),
        ("改进1: 添加止损5%", {'use_stop_loss': True, 'stop_loss_pct': 0.05}),
        ("改进2: 大盘趋势过滤", {'use_trend_filter': True, 'trend_data': trend_data}),
        ("改进3: 组合(止损+趋势过滤)", {'use_stop_loss': True, 'stop_loss_pct': 0.05, 'use_trend_filter': True, 'trend_data': trend_data}),
        ("改进4: 提高买点质量(RSI<40+量能放大)", {'use_quality_filter': True}),
        ("改进5: 全部组合", {'use_stop_loss': True, 'stop_loss_pct': 0.05, 'use_trend_filter': True, 'trend_data': trend_data, 'use_quality_filter': True}),
    ]
    
    print(f"\n{'策略':^35} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-" * 85)
    
    results = []
    for name, kwargs in strategies:
        trades = run_strategy(data, start_date, end_date, name, **kwargs)
        metrics = calculate_metrics(trades)
        results.append((name, metrics))
        
        print(f"{name:^35} {metrics['trades']:^8} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['totalReturn']:^10.1f} {metrics['avgReturn']:^10.2f}")
    
    print("\n" + "=" * 70)
    print("按年度分析各策略表现")
    print("=" * 70)
    
    for year_start, year_end, year_name in [("2024-01-01", "2024-12-31", "2024年(熊市)"), ("2025-01-01", "2025-12-31", "2025年(牛市)")]:
        print(f"\n{year_name}:")
        print(f"{'策略':^35} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10}")
        print("-" * 75)
        
        for name, kwargs in strategies:
            trades = run_strategy(data, year_start, year_end, name, **kwargs)
            metrics = calculate_metrics(trades)
            print(f"{name:^35} {metrics['trades']:^8} {metrics['winRate']:^8.1f} {metrics['profitFactor']:^8.2f} {metrics['totalReturn']:^10.1f}")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    baseline = results[0][1]
    print(f"\n原策略总收益: {baseline['totalReturn']:.1f}%")
    
    for name, metrics in results[1:]:
        diff = metrics['totalReturn'] - baseline['totalReturn']
        print(f"{name}: {metrics['totalReturn']:.1f}% (相比原策略: {diff:+.1f}%)")


if __name__ == "__main__":
    main()
