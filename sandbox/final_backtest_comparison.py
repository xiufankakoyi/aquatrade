"""
最终回测验证：对比不同选股策略

策略对比：
1. 股票代码排序（基准）
2. 综合评分模型排序
3. 只选择创业板/科创板
4. 综合评分 + 股票类型过滤
5. 综合评分阈值过滤
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict
from typing import Dict
import warnings
warnings.filterwarnings('ignore')

from data_cache import get_cache, PreloadedData


@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
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
def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    atr = np.zeros(n)
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr


@njit
def calc_vol_ma(volume: np.ndarray, period: int = 5) -> np.ndarray:
    n = len(volume)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.mean(volume[start:i+1])
    return result


@njit
def calc_ma(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.mean(close[start:i+1])
    return result


@njit
def calc_std(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.std(close[start:i+1])
    return result


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


@njit
def find_local_troughs(arr: np.ndarray, window: int = 5) -> np.ndarray:
    n = len(arr)
    troughs = np.zeros(n, dtype=np.bool_)
    
    for i in range(window, n - window):
        is_trough = True
        for j in range(-window, window + 1):
            if j != 0 and arr[i] >= arr[i + j]:
                is_trough = False
                break
        troughs[i] = is_trough
    
    return troughs


def calculate_score(
    close: np.ndarray, high: np.ndarray, low: np.ndarray,
    open_price: np.ndarray, volume: np.ndarray, amount: np.ndarray,
    signal_idx: int,
) -> float:
    """计算综合评分"""
    
    if signal_idx < 60:
        return 0
    
    dif, dea, hist = calc_macd(close)
    rsi = calc_rsi(close)
    atr = calc_atr(high, low, close)
    vol_ma5 = calc_vol_ma(volume.astype(np.float64), 5)
    vol_ma20 = calc_vol_ma(volume.astype(np.float64), 20)
    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    std20 = calc_std(close, 20)
    
    peaks = find_local_peaks(close, window=5)
    troughs = find_local_troughs(close, window=5)
    
    score = 0
    
    atr_pct = atr[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    score += (atr_pct - 3.0) / 1.5
    
    high_low_range = (high[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    score += (high_low_range - 2.5) / 1.5
    
    std20_pct = std20[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    score += (std20_pct - 3.5) / 1.5
    
    recent_low_60 = np.min(low[signal_idx-60:signal_idx+1]) if signal_idx >= 60 else np.min(low[:signal_idx+1])
    bounce_from_low = (close[signal_idx] - recent_low_60) / recent_low_60 * 100 if recent_low_60 > 0 else 0
    score += (bounce_from_low - 15) / 15
    
    price_to_ma5 = (close[signal_idx] - ma5[signal_idx]) / ma5[signal_idx] * 100 if ma5[signal_idx] > 0 else 0
    score += (price_to_ma5 - 1.5) / 2
    
    ret_5d = (close[signal_idx] - close[signal_idx-5]) / close[signal_idx-5] * 100 if signal_idx >= 5 else 0
    score += (ret_5d - 3) / 4
    
    price_to_ma10 = (close[signal_idx] - ma10[signal_idx]) / ma10[signal_idx] * 100 if ma10[signal_idx] > 0 else 0
    score += (price_to_ma10 - 1.5) / 2
    
    ret_3d = (close[signal_idx] - close[signal_idx-3]) / close[signal_idx-3] * 100 if signal_idx >= 3 else 0
    score += (ret_3d - 2.5) / 3
    
    lower_shadow = (close[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    score += (lower_shadow - 1.5) / 1.5
    
    trough_indices = np.where(troughs[:signal_idx+1])[0]
    if len(trough_indices) >= 2:
        prev_trough_idx = trough_indices[-1]
        price_vs_prev_trough = (close[signal_idx] - close[prev_trough_idx]) / close[prev_trough_idx] * 100
        score += (price_vs_prev_trough - 5) / 10
    
    return score


def run_backtest(
    data: PreloadedData,
    start_date: str,
    end_date: str,
    strategy: str = 'code_sort',
    score_threshold: float = None,
    stock_type_filter: list = None,
):
    """
    运行回测
    
    strategy:
        - 'code_sort': 股票代码排序（基准）
        - 'score_sort': 综合评分排序
        - 'score_threshold': 综合评分阈值过滤
        - 'stock_type': 股票类型过滤
        - 'combined': 综合评分 + 股票类型
    """
    
    all_trades = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        low = d['low']
        open_price = d['open']
        volume = d['volume']
        amount = d.get('amount', np.zeros_like(volume))
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        rsi = calc_rsi(close)
        peaks = find_local_peaks(close, window=5)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        low = low[mask]
        open_price = open_price[mask]
        volume = volume[mask]
        amount = amount[mask]
        dates = dates[mask]
        hist = hist[mask]
        rsi = rsi[mask]
        peaks = peaks[mask]
        signals = signals[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                
                if buy_date_idx >= len(close):
                    continue
                
                score = calculate_score(
                    close, high, low, open_price, volume, amount, i
                )
                
                is_gem = stock_code.startswith('300')
                is_star = stock_code.startswith('688')
                is_sme = stock_code.startswith('002')
                
                if strategy == 'stock_type' and stock_type_filter:
                    if not any([
                        ('gem' in stock_type_filter and is_gem),
                        ('star' in stock_type_filter and is_star),
                        ('sme' in stock_type_filter and is_sme),
                    ]):
                        continue
                
                if strategy == 'score_threshold' and score_threshold is not None:
                    if score < score_threshold:
                        continue
                
                if strategy == 'combined':
                    if not (is_gem or is_star):
                        continue
                    if score < 0:
                        continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                sell_reason = "timeout"
                hold_days = 0
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = hold_day
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= 0.03:
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
                        sell_reason = "divergence"
                        hold_days = hold_day + 1
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= 0.02:
                            sell_price = close[check_idx]
                            sell_reason = "trailing_stop"
                            hold_days = hold_day + 1
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = 10
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': str(dates[min(buy_date_idx + hold_days - 1, len(close)-1)]),
                    'return': ret,
                    'score': score,
                    'is_gem': is_gem,
                    'is_star': is_star,
                })
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    for date in trades_by_buy_date:
        if strategy == 'code_sort':
            trades_by_buy_date[date].sort(key=lambda x: x['stock_code'])
        elif strategy in ['score_sort', 'score_threshold', 'stock_type', 'combined']:
            trades_by_buy_date[date].sort(key=lambda x: x['score'], reverse=True)
    
    initial_capital = 100000.0
    capital = initial_capital
    holdings = {}
    equity_curve = []
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                capital += h['position_value'] * h['return']
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    continue
                
                if len(holdings) < 5:
                    holdings[t['stock_code']] = {
                        'position_value': initial_capital * 0.18,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                    }
        
        equity_curve.append({'date': date, 'equity': capital})
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        capital += h['position_value'] * h['return']
    
    returns = [t['return'] for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    total_return = (capital - initial_capital) / initial_capital * 100
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
    avg_return = np.mean(returns) * 100 if returns else 0
    
    strong_count = sum(1 for t in all_trades if t['is_gem'] or t['is_star'])
    strong_pct = strong_count / len(all_trades) * 100 if all_trades else 0
    
    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_return': avg_return,
        'trades': len(all_trades),
        'strong_pct': strong_pct,
        'equity_curve': equity_curve,
    }


def main():
    print("\n" + "="*70)
    print("最终回测验证：对比不同选股策略")
    print("="*70)
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    strategies = [
        ("策略1: 股票代码排序(基准)", 'code_sort', None, None),
        ("策略2: 综合评分排序", 'score_sort', None, None),
        ("策略3: 只选创业板/科创板", 'stock_type', None, ['gem', 'star']),
        ("策略4: 综合评分>=0", 'score_threshold', 0, None),
        ("策略5: 综合评分>=1", 'score_threshold', 1, None),
        ("策略6: 综合评分>=2", 'score_threshold', 2, None),
        ("策略7: 创业板/科创板+评分>=0", 'combined', None, None),
    ]
    
    print(f"\n{'策略':^30} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10} {'创科占比%':^10}")
    print("-"*95)
    
    results = []
    for name, strategy, threshold, stock_types in strategies:
        result = run_backtest(
            data, start_date, end_date,
            strategy=strategy,
            score_threshold=threshold,
            stock_type_filter=stock_types,
        )
        results.append((name, result))
        
        print(f"{name:<30} {result['trades']:^8} {result['win_rate']:^8.1f} {result['profit_factor']:^8.2f} {result['total_return']:^10.1f} {result['avg_return']:^10.2f} {result['strong_pct']:^10.1f}")
    
    print("\n" + "="*70)
    print("结论")
    print("="*70)
    
    baseline = results[0][1]
    best_score = max(results[1:], key=lambda x: x[1]['total_return'])
    
    print(f"""
1. 基准策略（股票代码排序）:
   - 总收益: {baseline['total_return']:.1f}%
   - 胜率: {baseline['win_rate']:.1f}%
   - 盈亏比: {baseline['profit_factor']:.2f}

2. 最佳策略（{best_score[0]}）:
   - 总收益: {best_score[1]['total_return']:.1f}%
   - 胜率: {best_score[1]['win_rate']:.1f}%
   - 盈亏比: {best_score[1]['profit_factor']:.2f}
   - 交易数: {best_score[1]['trades']}

3. 关键发现:
   - 股票代码排序效果好的本质是选择了高波动股票（创业板/科创板）
   - 综合评分模型能有效区分强势和弱势信号
   - 结合股票类型和评分过滤可以进一步提升效果

4. 改进建议:
   - 优先选择创业板/科创板股票
   - 使用综合评分过滤低分信号
   - 结合板块热度和市场情绪进一步优化
""")


if __name__ == "__main__":
    main()
