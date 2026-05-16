"""
MACD 四阴线策略 - 阶段1：机器学习条件筛选

目标：
1. 准备训练数据（MACD四阴线信号 + 各种特征 + 未来收益标签）
2. 使用随机森林分析特征重要性
3. 输出最佳条件建议
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from collections import defaultdict
import pickle


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


def detect_macd_signal(histogram: np.ndarray) -> np.ndarray:
    """检测 MACD 四阴线信号"""
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


def load_data(start_date: str, end_date: str):
    """加载数据"""
    from sandbox.top3_backtest_fixed import load_data as ld
    return ld(start_date, end_date)


def prepare_ml_data(daily_data: dict, forward_days: int = 10):
    """
    准备机器学习训练数据
    
    对于每个 MACD 四阴线信号，计算：
    - 当前特征值
    - 未来 N 天的收益（作为标签）
    """
    print("准备机器学习训练数据...")
    
    samples = []
    
    for sc, data in daily_data.items():
        dates = data['dates']
        close = data['close'].astype(np.float64)
        open_prices = data['open'].astype(np.float64)
        high = data['high'].astype(np.float64)
        low = data['low'].astype(np.float64)
        volume = data['volume'].astype(np.float64)
        
        if len(close) < 50:
            continue
        
        # 计算指标
        histogram = calc_macd(close)
        rsi = calc_rsi(close)
        ma5 = calc_ma(close, 5)
        ma10 = calc_ma(close, 10)
        ma20 = calc_ma(close, 20)
        vol_ma5 = calc_vol_ma(volume, 5)
        atr = calc_atr(high, low, close)
        
        # 检测信号
        signals = detect_macd_signal(histogram)
        
        for i in range(len(signals)):
            if not signals[i]:
                continue
            
            # 跳过信号日后一天没有数据的情况
            if i + 1 >= len(close) or i + forward_days >= len(close):
                continue
            
            # 买入价格：信号次日开盘价
            buy_price = open_prices[i + 1]
            if buy_price <= 0:
                continue
            
            # 卖出价格：N天后收盘价（或止盈止损）
            sell_price = close[i + forward_days]
            
            # 计算未来收益
            future_return = (sell_price - buy_price) / buy_price
            
            # 提取特征（在信号日）
            vs = calc_volatility_strength(close, high, low, i)
            rsi_val = rsi[i]
            volume_ratio = volume[i] / vol_ma5[i] if vol_ma5[i] > 0 else 1.0
            close_ma5_ratio = close[i] / ma5[i] if ma5[i] > 0 else 1.0
            close_ma10_ratio = close[i] / ma10[i] if ma10[i] > 0 else 1.0
            close_ma20_ratio = close[i] / ma20[i] if ma20[i] > 0 else 1.0
            ma5_ma10_diff = (ma5[i] - ma10[i]) / ma10[i] if ma10[i] > 0 else 0
            ma10_ma20_diff = (ma10[i] - ma20[i]) / ma20[i] if ma20[i] > 0 else 0
            bias = (close[i] - ma5[i]) / ma5[i] if ma5[i] > 0 else 0
            atr_ratio = atr[i] / close[i] if close[i] > 0 else 0
            histogram_val = histogram[i]
            
            sample = {
                'stock_code': sc,
                'signal_date': str(dates[i]),
                'vs_strength': vs,
                'rsi': rsi_val,
                'volume_ratio': volume_ratio,
                'close_ma5_ratio': close_ma5_ratio,
                'close_ma10_ratio': close_ma10_ratio,
                'close_ma20_ratio': close_ma20_ratio,
                'ma5_ma10_diff': ma5_ma10_diff,
                'ma10_ma20_diff': ma10_ma20_diff,
                'bias': bias,
                'atr_ratio': atr_ratio,
                'histogram': histogram_val,
                'future_return': future_return,
                'buy_price': buy_price,
                'sell_price': sell_price,
            }
            samples.append(sample)
    
    df = pd.DataFrame(samples)
    print(f"  总样本数: {len(df)}")
    return df


def train_and_analyze(df: pd.DataFrame):
    """训练随机森林并分析特征重要性"""
    print("\n训练随机森林模型...")
    
    try:
        from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("  需要安装 scikit-learn: pip install scikit-learn")
        return None
    
    # 特征列
    feature_cols = [
        'vs_strength', 'rsi', 'volume_ratio',
        'close_ma5_ratio', 'close_ma10_ratio', 'close_ma20_ratio',
        'ma5_ma10_diff', 'ma10_ma20_diff', 'bias', 'atr_ratio', 'histogram'
    ]
    
    X = df[feature_cols].values
    y_return = df['future_return'].values
    
    # 标签：未来收益（连续值）
    y_class = (df['future_return'] > 0.02).astype(int)  # 盈利超过2%为正样本
    
    # 处理缺失值
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    # 训练回归模型（预测未来收益）
    print("  训练回归模型...")
    rf_reg = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf_reg.fit(X, y_return)
    
    # 特征重要性（回归）
    importance_reg = pd.DataFrame({
        'feature': feature_cols,
        'importance_return': rf_reg.feature_importances_
    }).sort_values('importance_return', ascending=False)
    
    # 交叉验证
    cv_scores = cross_val_score(rf_reg, X, y_return, cv=5, scoring='r2')
    print(f"  回归模型 CV R²: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    # 训练分类模型（预测是否盈利）
    print("  训练分类模型...")
    rf_clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf_clf.fit(X, y_class)
    
    # 特征重要性（分类）
    importance_clf = pd.DataFrame({
        'feature': feature_cols,
        'importance_class': rf_clf.feature_importances_
    }).sort_values('importance_class', ascending=False)
    
    # 合并重要性
    importance = importance_reg.merge(importance_clf, on='feature')
    importance['importance_avg'] = (importance['importance_return'] + importance['importance_class']) / 2
    importance = importance.sort_values('importance_avg', ascending=False)
    
    return importance, rf_reg, rf_clf


def analyze_buy_conditions(df: pd.DataFrame, importance: pd.DataFrame):
    """分析买入条件"""
    print("\n" + "=" * 60)
    print("买入条件分析")
    print("=" * 60)
    
    # 基于特征重要性，分析最佳条件阈值
    top_features = importance.head(5)['feature'].tolist()
    
    print("\n特征重要性排名（平均）:")
    for i, row in importance.iterrows():
        print(f"  {row['feature']:20s}: {row['importance_avg']:.4f}")
    
    print(f"\nTop 5 重要特征: {top_features}")
    
    # 分析各特征的分布和最佳阈值
    print("\n特征分布分析:")
    for feat in top_features:
        if feat == 'vs_strength':
            print("\n--- 波动率强度 (vs_strength) ---")
            for threshold in [0, 0.3, 0.5, 0.7, 1.0]:
                mask = df['vs_strength'] >= threshold
                if mask.sum() > 0:
                    avg_ret = df.loc[mask, 'future_return'].mean()
                    win_rate = (df.loc[mask, 'future_return'] > 0).mean()
                    print(f"  VS >= {threshold}: 样本={mask.sum()}, 平均收益={avg_ret*100:.2f}%, 胜率={win_rate*100:.1f}%")
        
        elif feat == 'rsi':
            print("\n--- RSI ---")
            for threshold in [30, 40, 50, 60]:
                mask = df['rsi'] < threshold
                if mask.sum() > 0:
                    avg_ret = df.loc[mask, 'future_return'].mean()
                    win_rate = (df.loc[mask, 'future_return'] > 0).mean()
                    print(f"  RSI < {threshold}: 样本={mask.sum()}, 平均收益={avg_ret*100:.2f}%, 胜率={win_rate*100:.1f}%")
        
        elif feat == 'volume_ratio':
            print("\n--- 成交量放大 ---")
            for threshold in [1.0, 1.5, 2.0, 2.5]:
                mask = df['volume_ratio'] >= threshold
                if mask.sum() > 0:
                    avg_ret = df.loc[mask, 'future_return'].mean()
                    win_rate = (df.loc[mask, 'future_return'] > 0).mean()
                    print(f"  成交量 >= {threshold}x: 样本={mask.sum()}, 平均收益={avg_ret*100:.2f}%, 胜率={win_rate*100:.1f}%")
        
        elif feat == 'bias':
            print("\n--- 乖离率 (bias) ---")
            for threshold in [0, 0.02, 0.05]:
                mask = df['bias'] < threshold
                if mask.sum() > 0:
                    avg_ret = df.loc[mask, 'future_return'].mean()
                    win_rate = (df.loc[mask, 'future_return'] > 0).mean()
                    print(f"  bias < {threshold}: 样本={mask.sum()}, 平均收益={avg_ret*100:.2f}%, 胜率={win_rate*100:.1f}%")
        
        elif feat == 'close_ma5_ratio':
            print("\n--- 收盘价相对MA5位置 ---")
            for threshold in [0.95, 1.0, 1.02, 1.05]:
                mask = df['close_ma5_ratio'] >= threshold
                if mask.sum() > 0:
                    avg_ret = df.loc[mask, 'future_return'].mean()
                    win_rate = (df.loc[mask, 'future_return'] > 0).mean()
                    print(f"  close/MA5 >= {threshold}: 样本={mask.sum()}, 平均收益={avg_ret*100:.2f}%, 胜率={win_rate*100:.1f}%")
    
    return top_features


def main():
    print("=" * 60)
    print("MACD四阴线策略 - 阶段1：机器学习条件筛选")
    print("=" * 60)
    
    # 加载数据
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    daily_data = load_data(start_date, end_date)
    
    # 准备训练数据
    df = prepare_ml_data(daily_data, forward_days=10)
    
    # 训练模型并分析
    result = train_and_analyze(df)
    if result is None:
        print("需要安装 scikit-learn")
        return
    
    importance, rf_reg, rf_clf = result
    
    # 分析买入条件
    top_features = analyze_buy_conditions(df, importance)
    
    # 保存结果
    output_path = Path(__file__).parent / "ml_analysis_results.pkl"
    with open(output_path, 'wb') as f:
        pickle.dump({
            'importance': importance,
            'data': df,
            'model_reg': rf_reg,
            'model_clf': rf_clf,
            'top_features': top_features,
        }, f)
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
