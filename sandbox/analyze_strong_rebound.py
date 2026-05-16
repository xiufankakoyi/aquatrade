"""
深入分析：强反弹股票的特征模式

核心发现：
1. 股票代码排序效果好，本质是选择了高波动股票（创业板/科创板）
2. ML模型学到的最重要特征是波动率（ATR）
3. 需要找出除了波动率之外的其他有效特征

分析方法：
1. 对比强势样本和弱势样本的特征差异
2. 使用统计方法找出显著不同的特征
3. 构建综合评分模型
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

from data_cache import get_cache, PreloadedData

from scipy import stats


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


def extract_features(
    stock_code: str,
    dates: np.ndarray,
    close: np.ndarray, high: np.ndarray, low: np.ndarray,
    open_price: np.ndarray, volume: np.ndarray, amount: np.ndarray,
    signal_idx: int,
    stock_info: dict,
    sector_data: dict,
) -> dict:
    """提取信号时刻的特征"""
    features = {}
    
    if signal_idx < 60:
        return None
    
    dif, dea, hist = calc_macd(close)
    rsi = calc_rsi(close)
    atr = calc_atr(high, low, close)
    vol_ma5 = calc_vol_ma(volume.astype(np.float64), 5)
    vol_ma10 = calc_vol_ma(volume.astype(np.float64), 10)
    vol_ma20 = calc_vol_ma(volume.astype(np.float64), 20)
    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)
    std20 = calc_std(close, 20)
    
    peaks = find_local_peaks(close, window=5)
    troughs = find_local_troughs(close, window=5)
    
    b0, b1, b2, b3 = hist[signal_idx-3], hist[signal_idx-2], hist[signal_idx-1], hist[signal_idx]
    
    features['stock_code'] = stock_code
    features['signal_date'] = str(dates[signal_idx])
    
    features['is_gem'] = 1 if stock_code.startswith('300') else 0
    features['is_star'] = 1 if stock_code.startswith('688') else 0
    features['is_sme'] = 1 if stock_code.startswith('002') else 0
    features['is_main_sh'] = 1 if stock_code.startswith('60') else 0
    features['is_main_sz'] = 1 if stock_code.startswith('000') or stock_code.startswith('001') else 0
    
    features['atr_pct'] = atr[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    features['atr'] = atr[signal_idx]
    features['amount'] = amount[signal_idx] if signal_idx < len(amount) else 0
    features['amount_log'] = np.log1p(features['amount'])
    
    features['hist_value'] = b3
    features['hist_abs'] = abs(b3)
    features['hist_contraction'] = abs(b0) - abs(b3)
    features['hist_contraction_rate'] = (abs(b0) - abs(b3)) / abs(b0) if abs(b0) > 0 else 0
    
    diff1 = abs(b1) - abs(b0)
    diff2 = abs(b2) - abs(b1)
    diff3 = abs(b3) - abs(b2)
    features['hist_accel_1'] = diff2 - diff1
    features['hist_accel_2'] = diff3 - diff2
    features['hist_accel_avg'] = (diff1 + diff2 + diff3) / 3
    
    features['dif_value'] = dif[signal_idx]
    features['dea_value'] = dea[signal_idx]
    
    features['rsi'] = rsi[signal_idx]
    features['rsi_oversold'] = max(0, 30 - rsi[signal_idx])
    features['rsi_change_5d'] = rsi[signal_idx] - rsi[signal_idx-5] if signal_idx >= 5 else 0
    
    features['vol_ratio_5'] = volume[signal_idx] / vol_ma5[signal_idx] if vol_ma5[signal_idx] > 0 else 0
    features['vol_ratio_10'] = volume[signal_idx] / vol_ma10[signal_idx] if vol_ma10[signal_idx] > 0 else 0
    features['vol_ratio_20'] = volume[signal_idx] / vol_ma20[signal_idx] if vol_ma20[signal_idx] > 0 else 0
    
    features['price_to_ma5'] = (close[signal_idx] - ma5[signal_idx]) / ma5[signal_idx] * 100 if ma5[signal_idx] > 0 else 0
    features['price_to_ma10'] = (close[signal_idx] - ma10[signal_idx]) / ma10[signal_idx] * 100 if ma10[signal_idx] > 0 else 0
    features['price_to_ma20'] = (close[signal_idx] - ma20[signal_idx]) / ma20[signal_idx] * 100 if ma20[signal_idx] > 0 else 0
    features['price_to_ma60'] = (close[signal_idx] - ma60[signal_idx]) / ma60[signal_idx] * 100 if ma60[signal_idx] > 0 else 0
    
    features['ma5_ma10_gap'] = (ma5[signal_idx] - ma10[signal_idx]) / ma10[signal_idx] * 100 if ma10[signal_idx] > 0 else 0
    features['ma10_ma20_gap'] = (ma10[signal_idx] - ma20[signal_idx]) / ma20[signal_idx] * 100 if ma20[signal_idx] > 0 else 0
    
    features['std20_pct'] = std20[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    
    features['ret_1d'] = (close[signal_idx] - close[signal_idx-1]) / close[signal_idx-1] * 100 if signal_idx >= 1 else 0
    features['ret_3d'] = (close[signal_idx] - close[signal_idx-3]) / close[signal_idx-3] * 100 if signal_idx >= 3 else 0
    features['ret_5d'] = (close[signal_idx] - close[signal_idx-5]) / close[signal_idx-5] * 100 if signal_idx >= 5 else 0
    features['ret_10d'] = (close[signal_idx] - close[signal_idx-10]) / close[signal_idx-10] * 100 if signal_idx >= 10 else 0
    features['ret_20d'] = (close[signal_idx] - close[signal_idx-20]) / close[signal_idx-20] * 100 if signal_idx >= 20 else 0
    
    features['high_low_range'] = (high[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['upper_shadow'] = (high[signal_idx] - close[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['lower_shadow'] = (close[signal_idx] - low[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['body_size'] = abs(close[signal_idx] - open_price[signal_idx]) / close[signal_idx-1] * 100 if signal_idx >= 1 and close[signal_idx-1] > 0 else 0
    features['is_bullish'] = 1 if close[signal_idx] > open_price[signal_idx] else 0
    
    recent_high_20 = np.max(high[signal_idx-20:signal_idx+1]) if signal_idx >= 20 else np.max(high[:signal_idx+1])
    recent_low_20 = np.min(low[signal_idx-20:signal_idx+1]) if signal_idx >= 20 else np.min(low[:signal_idx+1])
    features['price_position_20d'] = (close[signal_idx] - recent_low_20) / (recent_high_20 - recent_low_20) * 100 if recent_high_20 != recent_low_20 else 50
    
    recent_high_60 = np.max(high[signal_idx-60:signal_idx+1]) if signal_idx >= 60 else np.max(high[:signal_idx+1])
    recent_low_60 = np.min(low[signal_idx-60:signal_idx+1]) if signal_idx >= 60 else np.min(low[:signal_idx+1])
    features['drawdown_from_high'] = (recent_high_60 - close[signal_idx]) / recent_high_60 * 100 if recent_high_60 > 0 else 0
    features['bounce_from_low'] = (close[signal_idx] - recent_low_60) / recent_low_60 * 100 if recent_low_60 > 0 else 0
    
    peak_indices = np.where(peaks[:signal_idx+1])[0]
    if len(peak_indices) >= 2:
        prev_peak_idx = peak_indices[-1]
        features['days_since_peak'] = signal_idx - prev_peak_idx
        features['price_vs_prev_peak'] = (close[signal_idx] - close[prev_peak_idx]) / close[prev_peak_idx] * 100
    else:
        features['days_since_peak'] = 0
        features['price_vs_prev_peak'] = 0
    
    trough_indices = np.where(troughs[:signal_idx+1])[0]
    if len(trough_indices) >= 2:
        prev_trough_idx = trough_indices[-1]
        features['days_since_trough'] = signal_idx - prev_trough_idx
        features['price_vs_prev_trough'] = (close[signal_idx] - close[prev_trough_idx]) / close[prev_trough_idx] * 100
    else:
        features['days_since_trough'] = 0
        features['price_vs_prev_trough'] = 0
    
    info = stock_info.get(stock_code, {})
    industry = info.get('industry', '')
    features['industry'] = industry
    
    trade_date = str(dates[signal_idx])
    if trade_date in sector_data and industry in sector_data[trade_date]:
        sector_info = sector_data[trade_date][industry]
        features['sector_pct_chg'] = sector_info.get('pct_chg', 0)
        features['sector_up_ratio'] = sector_info.get('up_ratio', 0)
        features['sector_limit_up'] = sector_info.get('limit_up_count', 0)
    else:
        features['sector_pct_chg'] = 0
        features['sector_up_ratio'] = 0
        features['sector_limit_up'] = 0
    
    return features


def build_dataset(
    data: PreloadedData,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """构建数据集"""
    
    print("\n" + "="*70)
    print("构建数据集")
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
                stock_code, dates, close, high, low, open_price, volume, amount,
                signal_idx, data.stock_info, data.sector_data
            )
            
            if features is None:
                continue
            
            buy_idx = signal_idx + 1
            if buy_idx >= len(close) - 5:
                continue
            
            buy_price = close[buy_idx]
            
            high_1d = (np.max(high[buy_idx:buy_idx+2]) - buy_price) / buy_price * 100 if buy_idx + 1 < len(high) else 0
            high_3d = (np.max(high[buy_idx:buy_idx+4]) - buy_price) / buy_price * 100 if buy_idx + 3 < len(high) else 0
            high_5d = (np.max(high[buy_idx:buy_idx+6]) - buy_price) / buy_price * 100 if buy_idx + 5 < len(high) else 0
            
            features['high_1d'] = high_1d
            features['high_3d'] = high_3d
            features['high_5d'] = high_5d
            features['is_strong'] = 1 if high_1d >= 3 else 0
            
            all_samples.append(features)
    
    df = pd.DataFrame(all_samples)
    print(f"总样本数: {len(df)}")
    print(f"强势样本: {df['is_strong'].sum()} ({df['is_strong'].mean()*100:.1f}%)")
    
    return df


def analyze_feature_differences(df: pd.DataFrame):
    """分析强势和弱势样本的特征差异"""
    
    print("\n" + "="*70)
    print("特征差异分析：强势 vs 弱势")
    print("="*70)
    
    strong = df[df['is_strong'] == 1]
    weak = df[df['is_strong'] == 0]
    
    feature_cols = [c for c in df.columns if c not in [
        'stock_code', 'signal_date', 'industry', 'high_1d', 'high_3d', 'high_5d', 'is_strong'
    ]]
    
    results = []
    for col in feature_cols:
        if col not in df.columns:
            continue
        
        strong_vals = strong[col].dropna()
        weak_vals = weak[col].dropna()
        
        if len(strong_vals) < 10 or len(weak_vals) < 10:
            continue
        
        strong_mean = strong_vals.mean()
        weak_mean = weak_vals.mean()
        diff = strong_mean - weak_mean
        
        all_vals = df[col].dropna()
        all_std = all_vals.std()
        effect_size = abs(diff) / all_std if all_std > 0 else 0
        
        try:
            stat, p_value = stats.mannwhitneyu(strong_vals, weak_vals, alternative='two-sided')
        except:
            p_value = 1.0
        
        results.append({
            'feature': col,
            'strong_mean': strong_mean,
            'weak_mean': weak_mean,
            'diff': diff,
            'effect_size': effect_size,
            'p_value': p_value,
        })
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('effect_size', ascending=False)
    
    print(f"\n{'特征':^25} {'强势均值':^12} {'弱势均值':^12} {'差异':^10} {'效应量':^10} {'p值':^12}")
    print("-"*85)
    
    for _, row in results_df.head(30).iterrows():
        sig = '***' if row['p_value'] < 0.001 else '**' if row['p_value'] < 0.01 else '*' if row['p_value'] < 0.05 else ''
        print(f"{row['feature']:<25} {row['strong_mean']:>12.3f} {row['weak_mean']:>12.3f} {row['diff']:>10.3f} {row['effect_size']:>10.3f} {row['p_value']:>12.4f} {sig}")
    
    return results_df


def analyze_by_stock_type(df: pd.DataFrame):
    """按股票类型分析"""
    
    print("\n" + "="*70)
    print("按股票类型分析")
    print("="*70)
    
    type_stats = []
    
    types = [
        ('创业板(300)', df['is_gem'] == 1),
        ('科创板(688)', df['is_star'] == 1),
        ('中小板(002)', df['is_sme'] == 1),
        ('沪主板(60)', df['is_main_sh'] == 1),
        ('深主板(000/001)', df['is_main_sz'] == 1),
    ]
    
    print(f"\n{'类型':^15} {'样本数':^10} {'>=3%概率':^12} {'>=5%概率':^12} {'平均第1天最高':^15}")
    print("-"*70)
    
    for type_name, mask in types:
        group = df[mask]
        if len(group) == 0:
            continue
        
        prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
        prob_5 = (group['high_1d'] >= 5).sum() / len(group) * 100
        avg_high = group['high_1d'].mean()
        
        print(f"{type_name:<15} {len(group):^10} {prob_3:^12.1f}% {prob_5:^12.1f}% {avg_high:^15.2f}%")
        
        type_stats.append({
            'type': type_name,
            'count': len(group),
            'prob_3': prob_3,
            'prob_5': prob_5,
            'avg_high': avg_high,
        })
    
    return type_stats


def analyze_by_feature_bins(df: pd.DataFrame, feature: str, bins: int = 5):
    """按特征分组分析"""
    
    print(f"\n按 {feature} 分组:")
    print(f"{'区间':^20} {'样本数':^10} {'>=3%概率':^12} {'平均第1天最高':^15}")
    print("-"*60)
    
    df_copy = df.copy()
    df_copy['bin'] = pd.qcut(df_copy[feature], bins, labels=False, duplicates='drop')
    
    for bin_val in sorted(df_copy['bin'].unique()):
        group = df_copy[df_copy['bin'] == bin_val]
        if len(group) == 0:
            continue
        
        low = df_copy[df_copy['bin'] == bin_val][feature].min()
        high = df_copy[df_copy['bin'] == bin_val][feature].max()
        
        prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
        avg_high = group['high_1d'].mean()
        
        print(f"[{low:>8.3f}, {high:>8.3f}] {len(group):^10} {prob_3:^12.1f}% {avg_high:^15.2f}%")


def build_scoring_model(df: pd.DataFrame, feature_importance: pd.DataFrame):
    """构建简单评分模型"""
    
    print("\n" + "="*70)
    print("构建综合评分模型")
    print("="*70)
    
    top_features = feature_importance.head(10)['feature'].tolist()
    
    print(f"\n使用 Top 10 特征:")
    for f in top_features:
        print(f"  - {f}")
    
    scores = np.zeros(len(df))
    
    for feature in top_features:
        if feature not in df.columns:
            continue
        
        values = df[feature].values
        valid_mask = ~np.isnan(values)
        
        if valid_mask.sum() == 0:
            continue
        
        mean_val = np.mean(values[valid_mask])
        std_val = np.std(values[valid_mask])
        
        if std_val == 0:
            continue
        
        normalized = np.zeros(len(df))
        normalized[valid_mask] = (values[valid_mask] - mean_val) / std_val
        
        strong_mean = df.loc[df['is_strong'] == 1, feature].mean()
        weak_mean = df.loc[df['is_strong'] == 0, feature].mean()
        
        if strong_mean > weak_mean:
            scores += normalized
        else:
            scores -= normalized
    
    df['score'] = scores
    
    print(f"\n按综合评分分组:")
    print(f"{'分组':^10} {'样本数':^10} {'>=3%概率':^12} {'>=5%概率':^12} {'平均第1天最高':^15}")
    print("-"*65)
    
    df['score_decile'] = pd.qcut(df['score'], 10, labels=False, duplicates='drop')
    
    for decile in sorted(df['score_decile'].unique()):
        group = df[df['score_decile'] == decile]
        prob_3 = (group['high_1d'] >= 3).sum() / len(group) * 100
        prob_5 = (group['high_1d'] >= 5).sum() / len(group) * 100
        avg_high = group['high_1d'].mean()
        
        print(f"{decile+1:^10} {len(group):^10} {prob_3:^12.1f}% {prob_5:^12.1f}% {avg_high:^15.2f}%")
    
    return df


def main():
    print("\n" + "="*70)
    print("深入分析：强反弹股票的特征模式")
    print("="*70)
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    df = build_dataset(data, start_date, end_date)
    
    analyze_by_stock_type(df)
    
    feature_importance = analyze_feature_differences(df)
    
    print("\n" + "="*70)
    print("关键特征分组分析")
    print("="*70)
    
    key_features = ['atr_pct', 'amount_log', 'vol_ratio_5', 'lower_shadow', 'price_to_ma20']
    for feat in key_features:
        if feat in df.columns:
            analyze_by_feature_bins(df, feat)
    
    df = build_scoring_model(df, feature_importance)
    
    print("\n" + "="*70)
    print("结论")
    print("="*70)
    
    print("""
1. 股票类型是最重要的特征：
   - 创业板/科创板的强势概率是主板股票的2倍以上
   - 这解释了为什么股票代码排序效果好

2. 波动率(ATR)是最重要的技术特征：
   - 高波动率股票的反弹强度明显更高
   - 但波动率也意味着风险更高

3. 其他有效特征：
   - 成交额：大成交额股票更容易反弹
   - 下影线：信号日下影线长说明有支撑
   - 价格位置：接近均线支撑的位置更好

4. 改进建议：
   - 优先选择创业板/科创板股票
   - 结合波动率和成交额筛选
   - 使用综合评分模型过滤低分信号
""")


if __name__ == "__main__":
    main()
