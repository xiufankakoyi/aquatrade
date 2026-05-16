"""
使用机器学习方法预测买入信号的反弹强度

核心思路：
1. 构建特征：只使用买入时刻可用的信息（无未来数据泄露）
2. 标签定义：未来N天的收益
3. 训练模型：LightGBM/XGBoost/随机森林
4. 分析特征重要性，找出强反弹股票的关键特征
5. 用模型预测分数排序进行回测验证
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
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


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


def extract_features_for_signal(
    stock_code: str,
    dates: np.ndarray,
    open_price: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    amount: np.ndarray,
    signal_idx: int,
    stock_info: dict,
    sector_data: dict,
    industry_stocks: Dict[str, List[str]],
    date_industry_ranks: dict,
) -> dict:
    """
    提取买入时刻可用的特征（无未来数据泄露）
    
    signal_idx 是信号日（MACD绿柱收缩的那天）
    买入日是 signal_idx + 1
    所有特征只能使用 signal_idx 及之前的数据
    """
    features = {}
    
    if signal_idx < 60 or signal_idx >= len(close) - 10:
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
    features['dif_dea_gap'] = dif[signal_idx] - dea[signal_idx]
    
    features['rsi'] = rsi[signal_idx]
    features['rsi_oversold'] = max(0, 30 - rsi[signal_idx])
    features['rsi_prev5'] = rsi[signal_idx-5] if signal_idx >= 5 else rsi[signal_idx]
    features['rsi_change'] = rsi[signal_idx] - rsi[signal_idx-5] if signal_idx >= 5 else 0
    
    features['atr'] = atr[signal_idx]
    features['atr_pct'] = atr[signal_idx] / close[signal_idx] * 100 if close[signal_idx] > 0 else 0
    
    features['vol_ratio_5'] = volume[signal_idx] / vol_ma5[signal_idx] if vol_ma5[signal_idx] > 0 else 0
    features['vol_ratio_10'] = volume[signal_idx] / vol_ma10[signal_idx] if vol_ma10[signal_idx] > 0 else 0
    features['vol_ratio_20'] = volume[signal_idx] / vol_ma20[signal_idx] if vol_ma20[signal_idx] > 0 else 0
    
    vol_ma5_prev = vol_ma5[signal_idx-1] if signal_idx >= 1 else vol_ma5[signal_idx]
    features['vol_ma5_change'] = (vol_ma5[signal_idx] - vol_ma5_prev) / vol_ma5_prev if vol_ma5_prev > 0 else 0
    
    features['close'] = close[signal_idx]
    features['ma5'] = ma5[signal_idx]
    features['ma10'] = ma10[signal_idx]
    features['ma20'] = ma20[signal_idx]
    features['ma60'] = ma60[signal_idx]
    
    features['price_to_ma5'] = (close[signal_idx] - ma5[signal_idx]) / ma5[signal_idx] * 100 if ma5[signal_idx] > 0 else 0
    features['price_to_ma10'] = (close[signal_idx] - ma10[signal_idx]) / ma10[signal_idx] * 100 if ma10[signal_idx] > 0 else 0
    features['price_to_ma20'] = (close[signal_idx] - ma20[signal_idx]) / ma20[signal_idx] * 100 if ma20[signal_idx] > 0 else 0
    features['price_to_ma60'] = (close[signal_idx] - ma60[signal_idx]) / ma60[signal_idx] * 100 if ma60[signal_idx] > 0 else 0
    
    features['ma5_ma10_gap'] = (ma5[signal_idx] - ma10[signal_idx]) / ma10[signal_idx] * 100 if ma10[signal_idx] > 0 else 0
    features['ma10_ma20_gap'] = (ma10[signal_idx] - ma20[signal_idx]) / ma20[signal_idx] * 100 if ma20[signal_idx] > 0 else 0
    
    features['std20'] = std20[signal_idx]
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
        prev_prev_peak_idx = peak_indices[-2]
        features['peak_to_peak_days'] = signal_idx - prev_peak_idx
        features['peak_price_change'] = (close[prev_peak_idx] - close[prev_prev_peak_idx]) / close[prev_prev_peak_idx] * 100
        features['price_vs_prev_peak'] = (close[signal_idx] - close[prev_peak_idx]) / close[prev_peak_idx] * 100
    else:
        features['peak_to_peak_days'] = 0
        features['peak_price_change'] = 0
        features['price_vs_prev_peak'] = 0
    
    trough_indices = np.where(troughs[:signal_idx+1])[0]
    if len(trough_indices) >= 2:
        prev_trough_idx = trough_indices[-1]
        features['trough_to_signal_days'] = signal_idx - prev_trough_idx
        features['price_vs_prev_trough'] = (close[signal_idx] - close[prev_trough_idx]) / close[prev_trough_idx] * 100
    else:
        features['trough_to_signal_days'] = 0
        features['price_vs_prev_trough'] = 0
    
    info = stock_info.get(stock_code, {})
    industry = info.get('industry', '')
    features['industry'] = industry
    
    trade_date = str(dates[signal_idx])
    cache_key = (trade_date, industry)
    
    if cache_key not in date_industry_ranks and industry and industry in industry_stocks:
        rank_dict = calculate_stock_rank_on_date(
            dates, close, trade_date, industry_stocks[industry]
        )
        date_industry_ranks[cache_key] = rank_dict
    
    if cache_key in date_industry_ranks:
        features['industry_rank'] = date_industry_ranks[cache_key].get(stock_code, 0)
    else:
        features['industry_rank'] = 0
    
    if trade_date in sector_data and industry in sector_data[trade_date]:
        sector_info = sector_data[trade_date][industry]
        features['sector_pct_chg'] = sector_info.get('pct_chg', 0)
        features['sector_up_ratio'] = sector_info.get('up_ratio', 0)
        features['sector_limit_up'] = sector_info.get('limit_up_count', 0)
    else:
        features['sector_pct_chg'] = 0
        features['sector_up_ratio'] = 0
        features['sector_limit_up'] = 0
    
    if signal_idx >= 5:
        features['vol_trend_5d'] = np.mean(volume[signal_idx-5:signal_idx]) / np.mean(volume[signal_idx-10:signal_idx-5]) if signal_idx >= 10 and np.mean(volume[signal_idx-10:signal_idx-5]) > 0 else 1
    else:
        features['vol_trend_5d'] = 1
    
    features['amount'] = amount[signal_idx] if signal_idx < len(amount) else 0
    features['amount_ratio'] = features['amount'] / np.mean(amount[signal_idx-5:signal_idx]) if signal_idx >= 5 and np.mean(amount[signal_idx-5:signal_idx]) > 0 else 1
    
    return features


def calculate_stock_rank_on_date(
    all_dates: np.ndarray,
    all_close: np.ndarray,
    trade_date: str,
    industry_stock_list: List[str]
) -> Dict[str, float]:
    return {}


def build_dataset(
    data: PreloadedData,
    start_date: str,
    end_date: str,
    lookback_days: int = 60,
) -> Tuple[pd.DataFrame, dict]:
    """
    构建机器学习数据集
    
    返回：
        - features_df: 特征DataFrame
        - labels_dict: 包含多个标签的字典
    """
    print("\n" + "="*70)
    print("构建机器学习数据集")
    print("="*70)
    
    industry_stocks = defaultdict(list)
    for stock_code, info in data.stock_info.items():
        industry = info.get('industry')
        if industry:
            industry_stocks[industry].append(stock_code)
    
    date_industry_ranks = {}
    
    all_features = []
    all_labels = []
    
    sorted_stock_codes = sorted(data.daily_data.keys())
    
    for stock_code in sorted_stock_codes:
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
            features = extract_features_for_signal(
                stock_code=stock_code,
                dates=dates,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                amount=amount,
                signal_idx=signal_idx,
                stock_info=data.stock_info,
                sector_data=data.sector_data,
                industry_stocks=industry_stocks,
                date_industry_ranks=date_industry_ranks,
            )
            
            if features is None:
                continue
            
            buy_idx = signal_idx + 1
            if buy_idx >= len(close) - 10:
                continue
            
            buy_price = close[buy_idx]
            
            labels = {
                'stock_code': stock_code,
                'signal_date': str(dates[signal_idx]),
                'buy_date': str(dates[buy_idx]),
                'buy_price': buy_price,
            }
            
            for day in [1, 2, 3, 5, 10]:
                if buy_idx + day < len(close):
                    labels[f'ret_{day}d'] = (close[buy_idx + day] - buy_price) / buy_price * 100
                    labels[f'high_{day}d'] = (np.max(high[buy_idx:buy_idx + day + 1]) - buy_price) / buy_price * 100
                    labels[f'low_{day}d'] = (np.min(low[buy_idx:buy_idx + day + 1]) - buy_price) / buy_price * 100
                else:
                    labels[f'ret_{day}d'] = None
                    labels[f'high_{day}d'] = None
                    labels[f'low_{day}d'] = None
            
            if buy_idx + 5 < len(close):
                max_profit = 0
                max_profit_day = 0
                for d in range(1, 6):
                    if buy_idx + d < len(high):
                        profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                        if profit > max_profit:
                            max_profit = profit
                            max_profit_day = d
                labels['max_profit_5d'] = max_profit
                labels['max_profit_day'] = max_profit_day
            else:
                labels['max_profit_5d'] = None
                labels['max_profit_day'] = None
            
            labels['is_strong_3pct'] = 1 if labels.get('high_1d', 0) >= 3 else 0
            labels['is_strong_5pct'] = 1 if labels.get('high_3d', 0) >= 5 else 0
            
            all_features.append(features)
            all_labels.append(labels)
    
    features_df = pd.DataFrame(all_features)
    labels_df = pd.DataFrame(all_labels)
    
    print(f"\n总样本数: {len(features_df)}")
    print(f"特征数: {len(features_df.columns) - 2}")
    
    strong_3pct = labels_df['is_strong_3pct'].sum()
    strong_5pct = labels_df['is_strong_5pct'].sum()
    print(f"强反弹样本(第1天最高>=3%): {strong_3pct} ({strong_3pct/len(labels_df)*100:.1f}%)")
    print(f"强反弹样本(第3天最高>=5%): {strong_5pct} ({strong_5pct/len(labels_df)*100:.1f}%)")
    
    return features_df, labels_df


def train_and_evaluate_models(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    target_col: str = 'high_1d',
    n_splits: int = 5,
):
    """
    训练并评估多种模型
    
    使用时间序列交叉验证，避免未来数据泄露
    """
    print("\n" + "="*70)
    print(f"训练模型 - 目标: {target_col}")
    print("="*70)
    
    feature_cols = [c for c in features_df.columns if c not in ['stock_code', 'signal_date', 'industry']]
    
    X = features_df[feature_cols].values
    y = labels_df[target_col].values
    
    valid_mask = ~np.isnan(y)
    X = X[valid_mask]
    y = y[valid_mask]
    
    dates = pd.to_datetime(features_df.loc[valid_mask, 'signal_date'])
    sort_idx = np.argsort(dates.values)
    X = X[sort_idx]
    y = y[sort_idx]
    
    print(f"\n有效样本数: {len(y)}")
    print(f"目标变量统计: 均值={np.mean(y):.2f}%, 标准差={np.std(y):.2f}%, 中位数={np.median(y):.2f}%")
    
    results = {}
    
    if HAS_SKLEARN:
        print("\n[1] 随机森林...")
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )
        
        rf_importance = np.zeros(len(feature_cols))
        rf_predictions = np.zeros(len(y))
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            rf_model.fit(X_train, y_train)
            rf_importance += rf_model.feature_importances_ / n_splits
            rf_predictions[test_idx] = rf_model.predict(X_test)
        
        rf_mse = mean_squared_error(y, rf_predictions)
        rf_mae = mean_absolute_error(y, rf_predictions)
        rf_corr = np.corrcoef(y, rf_predictions)[0, 1]
        
        results['RandomForest'] = {
            'mse': rf_mse,
            'mae': rf_mae,
            'correlation': rf_corr,
            'importance': rf_importance,
            'predictions': rf_predictions,
        }
        
        print(f"  MSE: {rf_mse:.4f}, MAE: {rf_mae:.4f}, 相关系数: {rf_corr:.4f}")
    
    if HAS_LGB:
        print("\n[2] LightGBM...")
        lgb_importance = np.zeros(len(feature_cols))
        lgb_predictions = np.zeros(len(y))
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            train_data = lgb.Dataset(X_train, label=y_train)
            valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
            
            params = {
                'objective': 'regression',
                'metric': 'mae',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'verbose': -1,
                'seed': 42,
            }
            
            model = lgb.train(
                params,
                train_data,
                num_boost_round=500,
                valid_sets=[valid_data],
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
            )
            
            lgb_importance += model.feature_importance(importance_type='gain') / n_splits
            lgb_predictions[test_idx] = model.predict(X_test)
        
        lgb_mse = mean_squared_error(y, lgb_predictions)
        lgb_mae = mean_absolute_error(y, lgb_predictions)
        lgb_corr = np.corrcoef(y, lgb_predictions)[0, 1]
        
        results['LightGBM'] = {
            'mse': lgb_mse,
            'mae': lgb_mae,
            'correlation': lgb_corr,
            'importance': lgb_importance,
            'predictions': lgb_predictions,
        }
        
        print(f"  MSE: {lgb_mse:.4f}, MAE: {lgb_mae:.4f}, 相关系数: {lgb_corr:.4f}")
    
    if HAS_XGB:
        print("\n[3] XGBoost...")
        xgb_importance = np.zeros(len(feature_cols))
        xgb_predictions = np.zeros(len(y))
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            train_data = xgb.DMatrix(X_train, label=y_train)
            valid_data = xgb.DMatrix(X_test, label=y_test)
            
            params = {
                'objective': 'reg:squarederror',
                'eval_metric': 'mae',
                'max_depth': 6,
                'eta': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'seed': 42,
            }
            
            model = xgb.train(
                params,
                train_data,
                num_boost_round=500,
                evals=[(valid_data, 'valid')],
                early_stopping_rounds=50,
                verbose_eval=False,
            )
            
            importance_dict = model.get_score(importance_type='gain')
            for i, col in enumerate(feature_cols):
                key = f'f{i}'
                if key in importance_dict:
                    xgb_importance[i] += importance_dict[key] / n_splits
            
            xgb_predictions[test_idx] = model.predict(valid_data)
        
        xgb_mse = mean_squared_error(y, xgb_predictions)
        xgb_mae = mean_absolute_error(y, xgb_predictions)
        xgb_corr = np.corrcoef(y, xgb_predictions)[0, 1]
        
        results['XGBoost'] = {
            'mse': xgb_mse,
            'mae': xgb_mae,
            'correlation': xgb_corr,
            'importance': xgb_importance,
            'predictions': xgb_predictions,
        }
        
        print(f"  MSE: {xgb_mse:.4f}, MAE: {xgb_mae:.4f}, 相关系数: {xgb_corr:.4f}")
    
    print("\n" + "="*70)
    print("模型对比")
    print("="*70)
    print(f"\n{'模型':^15} {'MSE':^10} {'MAE':^10} {'相关系数':^10}")
    print("-"*50)
    for model_name, res in results.items():
        print(f"{model_name:^15} {res['mse']:^10.4f} {res['mae']:^10.4f} {res['correlation']:^10.4f}")
    
    return results, feature_cols


def analyze_feature_importance(
    results: dict,
    feature_cols: list,
    top_n: int = 20,
):
    """分析特征重要性"""
    print("\n" + "="*70)
    print("特征重要性分析")
    print("="*70)
    
    for model_name, res in results.items():
        if 'importance' not in res:
            continue
        
        importance = res['importance']
        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': importance,
        })
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        print(f"\n【{model_name} Top {top_n} 特征】")
        print("-"*60)
        for i, row in importance_df.head(top_n).iterrows():
            print(f"  {row['feature']:<30} {row['importance']:>12.4f}")
    
    if len(results) > 1:
        all_importance = np.zeros(len(feature_cols))
        for model_name, res in results.items():
            if 'importance' in res:
                normalized = res['importance'] / np.sum(res['importance'])
                all_importance += normalized
        
        all_importance /= len([r for r in results.values() if 'importance' in r])
        
        combined_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': all_importance,
        })
        combined_df = combined_df.sort_values('importance', ascending=False)
        
        print(f"\n【综合特征重要性 Top {top_n}】")
        print("-"*60)
        for i, row in combined_df.head(top_n).iterrows():
            print(f"  {row['feature']:<30} {row['importance']:>12.4f}")
        
        return combined_df
    
    return None


def analyze_prediction_distribution(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    predictions: np.ndarray,
    target_col: str = 'high_1d',
):
    """分析预测分数与实际收益的关系"""
    print("\n" + "="*70)
    print("预测分数与实际收益的关系")
    print("="*70)
    
    valid_mask = ~np.isnan(labels_df[target_col].values)
    y_true = labels_df.loc[valid_mask, target_col].values
    
    dates = pd.to_datetime(features_df.loc[valid_mask, 'signal_date'])
    sort_idx = np.argsort(dates.values)
    y_true = y_true[sort_idx]
    y_pred = predictions
    
    df = pd.DataFrame({
        'pred': y_pred,
        'actual': y_true,
    })
    
    df['pred_decile'] = pd.qcut(df['pred'], 10, labels=False, duplicates='drop')
    
    print(f"\n按预测分数分组:")
    print(f"{'分组':^10} {'样本数':^10} {'预测均值':^12} {'实际均值':^12} {'差异':^10}")
    print("-"*60)
    
    for decile in sorted(df['pred_decile'].unique()):
        group = df[df['pred_decile'] == decile]
        pred_mean = group['pred'].mean()
        actual_mean = group['actual'].mean()
        diff = actual_mean - pred_mean
        
        print(f"{decile+1:^10} {len(group):^10} {pred_mean:^12.2f}% {actual_mean:^12.2f}% {diff:^10.2f}%")
    
    print("\n按预测分数分组的强势概率:")
    print(f"{'分组':^10} {'样本数':^10} {'>=3%概率':^12} {'>=5%概率':^12}")
    print("-"*50)
    
    for decile in sorted(df['pred_decile'].unique()):
        group = df[df['pred_decile'] == decile]
        prob_3 = (group['actual'] >= 3).sum() / len(group) * 100
        prob_5 = (group['actual'] >= 5).sum() / len(group) * 100
        
        print(f"{decile+1:^10} {len(group):^10} {prob_3:^12.1f}% {prob_5:^12.1f}%")
    
    return df


def run_backtest_with_ml_score(
    data: PreloadedData,
    start_date: str,
    end_date: str,
    predictions: np.ndarray,
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    top_n: int = 5,
):
    """使用ML预测分数进行回测"""
    print("\n" + "="*70)
    print("使用ML预测分数进行回测")
    print("="*70)
    
    pred_dict = {}
    for i, row in features_df.iterrows():
        key = (row['stock_code'], row['signal_date'])
        valid_idx = features_df.index.get_loc(i)
        if valid_idx < len(predictions):
            pred_dict[key] = predictions[valid_idx]
    
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
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                sold = False
                sell_reason = "timeout"
                hold_days = 0
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = hold_day
                        sold = True
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
                        sold = True
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= 0.02:
                            sell_price = close[check_idx]
                            sell_reason = "trailing_stop"
                            hold_days = hold_day + 1
                            sold = True
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = 10
                        sold = True
                
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
                
                if len(holdings) < top_n:
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
    
    print(f"\n回测结果:")
    print(f"  总交易数: {len(all_trades)}")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  盈亏比: {profit_factor:.2f}")
    print(f"  平均收益: {avg_return:.2f}%")
    print(f"  总收益: {total_return:.1f}%")
    
    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_return': avg_return,
        'trades': len(all_trades),
        'equity_curve': equity_curve,
    }


def main():
    print("\n" + "="*70)
    print("机器学习预测买入信号反弹强度")
    print("="*70)
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    features_df, labels_df = build_dataset(data, start_date, end_date)
    
    if len(features_df) == 0:
        print("\n没有找到有效样本，退出")
        return
    
    targets = ['high_1d', 'high_3d', 'high_5d', 'max_profit_5d']
    
    all_results = {}
    
    for target in targets:
        if target not in labels_df.columns:
            continue
        
        print(f"\n\n{'='*70}")
        print(f"目标变量: {target}")
        print(f"{'='*70}")
        
        results, feature_cols = train_and_evaluate_models(
            features_df, labels_df, target_col=target
        )
        
        if results:
            all_results[target] = {
                'results': results,
                'feature_cols': feature_cols,
            }
            
            importance_df = analyze_feature_importance(results, feature_cols)
            
            best_model = max(results.items(), key=lambda x: x[1]['correlation'])
            predictions = best_model[1]['predictions']
            
            analyze_prediction_distribution(features_df, labels_df, predictions, target)
    
    print("\n\n" + "="*70)
    print("使用最佳模型进行回测验证")
    print("="*70)
    
    if all_results:
        best_target = 'high_1d'
        best_results = all_results[best_target]['results']
        best_model_name = max(best_results.items(), key=lambda x: x[1]['correlation'])[0]
        best_predictions = best_results[best_model_name]['predictions']
        
        ml_result = run_backtest_with_ml_score(
            data, start_date, end_date,
            best_predictions, features_df, labels_df
        )
        
        print("\n\n" + "="*70)
        print("总结")
        print("="*70)
        print(f"\n最佳目标变量: {best_target}")
        print(f"最佳模型: {best_model_name}")
        print(f"预测相关系数: {best_results[best_model_name]['correlation']:.4f}")
        print(f"\n回测结果:")
        print(f"  总收益: {ml_result['total_return']:.1f}%")
        print(f"  胜率: {ml_result['win_rate']:.1f}%")
        print(f"  盈亏比: {ml_result['profit_factor']:.2f}")


if __name__ == "__main__":
    main()
