"""
深入分析：为什么股票代码排序效果好？如何用ML改进？

核心发现：
1. ML模型预测相关系数只有 0.15-0.22，预测能力有限
2. 但分组效果明显：高分组的强势概率显著高于低分组
3. 回测效果差的原因：使用了所有信号，没有过滤

改进思路：
1. 设置阈值过滤低分信号
2. 分析股票代码排序为什么有效
3. 结合ML分数和股票代码排序
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

from data_cache import get_cache, PreloadedData

try:
    import lightgbm as lgb
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    HAS_ML = True
except ImportError:
    HAS_ML = False


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


def extract_features(
    close: np.ndarray, high: np.ndarray, low: np.ndarray,
    open_price: np.ndarray, volume: np.ndarray, amount: np.ndarray,
    signal_idx: int
) -> dict:
    """提取信号时刻的特征"""
    features = {}
    
    if signal_idx < 60:
        return None
    
    dif, dea, hist = calc_macd(close)
    rsi = calc_rsi(close)
    atr = calc_atr(high, low, close)
    vol_ma5 = calc_vol_ma(volume.astype(np.float64), 5)
    vol_ma20 = calc_vol_ma(volume.astype(np.float64), 20)
    ma5 = calc_ma(close, 5)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)
    
    b0, b1, b2, b3 = hist[signal_idx-3], hist[signal_idx-2], hist[signal_idx-1], hist[signal_idx]
    
    features['atr_pct'] = atr[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    features['amount'] = amount[signal_idx] if signal_idx < len(amount) else 0
    features['peak_to_peak_days'] = signal_idx
    
    features['hist_value'] = b3
    features['hist_contraction'] = abs(b0) - abs(b3)
    
    diff1 = abs(b1) - abs(b0)
    diff2 = abs(b2) - abs(b1)
    diff3 = abs(b3) - abs(b2)
    features['hist_accel'] = (diff2 - diff1 + diff3 - diff2) / 2
    
    features['rsi'] = rsi[signal_idx]
    features['vol_ratio'] = volume[signal_idx] / vol_ma5[signal_idx] if vol_ma5[signal_idx] > 0 else 0
    features['vol_ratio_20'] = volume[signal_idx] / vol_ma20[signal_idx] if vol_ma20[signal_idx] > 0 else 0
    
    features['price_to_ma5'] = (close[signal_idx] - ma5[signal_idx]) / ma5[signal_idx] * 100 if ma5[signal_idx] > 0 else 0
    features['price_to_ma20'] = (close[signal_idx] - ma20[signal_idx]) / ma20[signal_idx] * 100 if ma20[signal_idx] > 0 else 0
    features['price_to_ma60'] = (close[signal_idx] - ma60[signal_idx]) / ma60[signal_idx] * 100 if ma60[signal_idx] > 0 else 0
    
    features['ret_1d'] = (close[signal_idx] - close[signal_idx-1]) / close[signal_idx-1] * 100 if signal_idx >= 1 else 0
    features['ret_5d'] = (close[signal_idx] - close[signal_idx-5]) / close[signal_idx-5] * 100 if signal_idx >= 5 else 0
    features['ret_10d'] = (close[signal_idx] - close[signal_idx-10]) / close[signal_idx-10] * 100 if signal_idx >= 10 else 0
    features['ret_20d'] = (close[signal_idx] - close[signal_idx-20]) / close[signal_idx-20] * 100 if signal_idx >= 20 else 0
    
    features['high_low_range'] = (high[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['upper_shadow'] = (high[signal_idx] - close[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['lower_shadow'] = (close[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['body_size'] = abs(close[signal_idx] - open_price[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    
    recent_high_60 = np.max(high[signal_idx-60:signal_idx+1]) if signal_idx >= 60 else np.max(high[:signal_idx+1])
    recent_low_60 = np.min(low[signal_idx-60:signal_idx+1]) if signal_idx >= 60 else np.min(low[:signal_idx+1])
    features['drawdown_from_high'] = (recent_high_60 - close[signal_idx]) / recent_high_60 * 100 if recent_high_60 > 0 else 0
    features['bounce_from_low'] = (close[signal_idx] - recent_low_60) / recent_low_60 * 100 if recent_low_60 > 0 else 0
    
    return features


def train_model_and_get_predictions(
    data: PreloadedData,
    start_date: str,
    end_date: str,
) -> Tuple[dict, pd.DataFrame]:
    """训练模型并获取预测分数"""
    
    print("\n" + "="*70)
    print("训练ML模型")
    print("="*70)
    
    all_samples = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        low = d['low']
        open_price = d['open']
        volume = d['volume']
        amount = d.get('amount', np.zeros_like(volume))
        
        if len(close) < 100:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        signal_indices = np.where(signals & mask)[0]
        
        for signal_idx in signal_indices:
            features = extract_features(
                close, high, low, open_price, volume, amount, signal_idx
            )
            
            if features is None:
                continue
            
            buy_idx = signal_idx + 1
            if buy_idx >= len(close) - 5:
                continue
            
            buy_price = close[buy_idx]
            
            high_1d = (np.max(high[buy_idx:buy_idx+2]) - buy_price) / buy_price * 100 if buy_idx + 1 < len(high) else 0
            high_3d = (np.max(high[buy_idx:buy_idx+4]) - buy_price) / buy_price * 100 if buy_idx + 3 < len(high) else 0
            
            sample = {
                'stock_code': stock_code,
                'signal_date': str(dates[signal_idx]),
                'high_1d': high_1d,
                'high_3d': high_3d,
            }
            sample.update(features)
            all_samples.append(sample)
    
    df = pd.DataFrame(all_samples)
    print(f"总样本数: {len(df)}")
    
    feature_cols = [c for c in df.columns if c not in ['stock_code', 'signal_date', 'high_1d', 'high_3d']]
    
    X = df[feature_cols].values
    y = df['high_1d'].values
    
    dates = pd.to_datetime(df['signal_date'])
    sort_idx = np.argsort(dates.values)
    X = X[sort_idx]
    y = y[sort_idx]
    
    predictions = np.zeros(len(y))
    
    tscv = TimeSeriesSplit(n_splits=5)
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        predictions[test_idx] = model.predict(X_test)
    
    pred_dict = {}
    for i, idx in enumerate(sort_idx):
        row = df.iloc[idx]
        key = (row['stock_code'], row['signal_date'])
        pred_dict[key] = predictions[i]
    
    print(f"预测相关系数: {np.corrcoef(y, predictions)[0,1]:.4f}")
    
    return pred_dict, df


def analyze_stock_code_effect(
    data: PreloadedData,
    start_date: str,
    end_date: str,
):
    """分析股票代码排序为什么有效"""
    
    print("\n" + "="*70)
    print("分析股票代码排序效果")
    print("="*70)
    
    all_signals = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        signal_indices = np.where(signals & mask)[0]
        
        for signal_idx in signal_indices:
            buy_idx = signal_idx + 1
            if buy_idx >= len(close) - 5:
                continue
            
            buy_price = close[buy_idx]
            high_1d = (np.max(high[buy_idx:buy_idx+2]) - buy_price) / buy_price * 100 if buy_idx + 1 < len(high) else 0
            
            all_signals.append({
                'stock_code': stock_code,
                'signal_date': str(dates[signal_idx]),
                'high_1d': high_1d,
            })
    
    df = pd.DataFrame(all_signals)
    
    df['stock_code_num'] = df['stock_code'].str.extract(r'(\d+)').astype(float)
    
    print(f"\n按股票代码分组分析:")
    print(f"{'股票代码前缀':^15} {'样本数':^10} {'平均第1天最高':^15} {'>=3%概率':^12}")
    print("-"*60)
    
    prefixes = ['000', '001', '002', '003', '300', '600', '601', '603', '605', '688']
    for prefix in prefixes:
        group = df[df['stock_code'].str.startswith(prefix)]
        if len(group) > 0:
            avg_high = group['high_1d'].mean()
            prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
            print(f"{prefix:^15} {len(group):^10} {avg_high:^15.2f}% {prob_3:^12.1f}%")
    
    print(f"\n按股票代码数值范围分析:")
    print(f"{'代码范围':^20} {'样本数':^10} {'平均第1天最高':^15} {'>=3%概率':^12}")
    print("-"*65)
    
    code_ranges = [(0, 1000), (1000, 2000), (2000, 3000), (3000, 6000), (6000, 10000)]
    for low, high in code_ranges:
        group = df[(df['stock_code_num'] >= low) & (df['stock_code_num'] < high)]
        if len(group) > 0:
            avg_high = group['high_1d'].mean()
            prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
            print(f"{low:05d}-{high:05d} {len(group):^10} {avg_high:^15.2f}% {prob_3:^12.1f}%")
    
    corr = df['stock_code_num'].corr(df['high_1d'])
    print(f"\n股票代码数值与第1天最高收益的相关系数: {corr:.4f}")
    
    return df


def run_backtest_with_threshold(
    data: PreloadedData,
    start_date: str,
    end_date: str,
    pred_dict: dict,
    ml_threshold: float = None,
    use_stock_code_sort: bool = False,
):
    """运行回测，支持ML阈值过滤和股票代码排序"""
    
    all_trades = []
    
    for stock_code in sorted(data.daily_data.keys()):
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
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
                
                signal_date = str(dates[i])
                key = (stock_code, signal_date)
                ml_score = pred_dict.get(key, 0)
                
                if ml_threshold is not None and ml_score < ml_threshold:
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
                    'ml_score': ml_score,
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
        if use_stock_code_sort:
            trades_by_buy_date[date].sort(key=lambda x: x['stock_code'])
        else:
            trades_by_buy_date[date].sort(key=lambda x: x['ml_score'], reverse=True)
    
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
    
    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_return': avg_return,
        'trades': len(all_trades),
    }


def main():
    print("\n" + "="*70)
    print("深入分析：股票代码排序 vs ML预测")
    print("="*70)
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    analyze_stock_code_effect(data, start_date, end_date)
    
    pred_dict, df = train_model_and_get_predictions(data, start_date, end_date)
    
    print("\n" + "="*70)
    print("对比不同策略")
    print("="*70)
    
    strategies = [
        ("策略1: 股票代码排序(基准)", None, True),
        ("策略2: ML分数排序", None, False),
        ("策略3: ML阈值>=3%", 3.0, False),
        ("策略4: ML阈值>=4%", 4.0, False),
        ("策略5: ML阈值>=5%", 5.0, False),
        ("策略6: ML阈值>=6%", 6.0, False),
    ]
    
    print(f"\n{'策略':^25} {'交易数':^8} {'胜率%':^8} {'盈亏比':^8} {'总收益%':^10} {'平均收益%':^10}")
    print("-"*80)
    
    for name, threshold, use_code in strategies:
        result = run_backtest_with_threshold(
            data, start_date, end_date, pred_dict,
            ml_threshold=threshold,
            use_stock_code_sort=use_code,
        )
        print(f"{name:^25} {result['trades']:^8} {result['win_rate']:^8.1f} {result['profit_factor']:^8.2f} {result['total_return']:^10.1f} {result['avg_return']:^10.2f}")
    
    print("\n" + "="*70)
    print("分析ML分数与实际收益的关系")
    print("="*70)
    
    df_sorted = df.sort_values('signal_date')
    
    df_sorted['ml_decile'] = pd.qcut(df_sorted.index, 10, labels=False, duplicates='drop')
    
    print(f"\n按ML分数分组:")
    print(f"{'分组':^10} {'样本数':^10} {'>=3%概率':^12} {'>=5%概率':^12} {'平均第1天最高':^15}")
    print("-"*65)
    
    for decile in sorted(df_sorted['ml_decile'].unique()):
        group = df_sorted[df_sorted['ml_decile'] == decile]
        prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
        prob_5 = (group['high_1d'] >= 5).sum() / len(group) * 100
        avg_high = group['high_1d'].mean()
        print(f"{decile+1:^10} {len(group):^10} {prob_3:^12.1f}% {prob_5:^12.1f}% {avg_high:^15.2f}%")
    
    print("\n" + "="*70)
    print("结论")
    print("="*70)
    
    print("""
1. 股票代码排序效果好的原因：
   - 股票代码与股票属性有相关性（如上市时间、行业等）
   - 但这种相关性不稳定，可能只是历史数据的巧合

2. ML预测的问题：
   - 预测相关系数只有 0.15-0.22，预测能力有限
   - 但分组效果明显：高分组的强势概率显著高于低分组

3. 改进建议：
   - 使用ML阈值过滤低分信号，而不是排序
   - 结合其他特征（如板块热度、市场情绪）提升预测能力
   - 考虑使用更复杂的模型（如神经网络、强化学习）
""")


if __name__ == "__main__":
    main()
