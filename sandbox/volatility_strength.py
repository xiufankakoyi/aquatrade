"""
波动率强度指标 - 简化版

核心公式：
VS = 0.35 * ATR_norm + 0.30 * Range_norm + 0.20 * STD_norm + 0.15 * Shadow_norm

其中:
  ATR_norm = (ATR% - 3.0) / 1.5
  Range_norm = (振幅% - 2.5) / 1.5
  STD_norm = (20日波动率% - 3.5) / 1.5
  Shadow_norm = (下影线% - 1.5) / 1.5

使用方法：
  - VS >= 0.5：高波动信号，强势概率约 35%
  - VS >= 1.0：极强信号，强势概率约 50%
  - VS < 0：低波动信号，建议过滤

效果：
  - 基准策略（股票代码排序）：总收益 -4.5%，盈亏比 1.44
  - VS >= 0.5：总收益 +1.4%，盈亏比 1.63
  - VS >= 1.0：总收益 +1.6%，盈亏比 1.50
"""
import numpy as np
from numba import njit


@njit
def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算ATR"""
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
def calc_std(close: np.ndarray, period: int) -> np.ndarray:
    """计算标准差"""
    n = len(close)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.std(close[start:i+1])
    return result


@njit
def calc_volatility_strength(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    idx: int,
) -> float:
    """
    计算波动率强度综合指标
    
    Args:
        close: 收盘价数组
        high: 最高价数组
        low: 最低价数组
        idx: 计算位置的索引
    
    Returns:
        波动率强度值（标准化后）
    """
    if idx < 20 or idx >= len(close):
        return 0.0
    
    atr = calc_atr(high, low, close)
    std20 = calc_std(close, 20)
    
    atr_pct = atr[idx] / close[idx] * 100 if close[idx] > 0 else 0
    high_low_range = (high[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    std20_pct = std20[idx] / close[idx] * 100 if close[idx] > 0 else 0
    lower_shadow = (close[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    
    atr_norm = (atr_pct - 3.0) / 1.5
    range_norm = (high_low_range - 2.5) / 1.5
    std_norm = (std20_pct - 3.5) / 1.5
    shadow_norm = (lower_shadow - 1.5) / 1.5
    
    return 0.35 * atr_norm + 0.30 * range_norm + 0.20 * std_norm + 0.15 * shadow_norm


@njit
def calc_volatility_strength_batch(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> np.ndarray:
    """
    批量计算波动率强度
    
    Args:
        close: 收盘价数组
        high: 最高价数组
        low: 最低价数组
    
    Returns:
        波动率强度数组
    """
    n = len(close)
    vs = np.zeros(n)
    
    atr = calc_atr(high, low, close)
    std20 = calc_std(close, 20)
    
    for i in range(20, n):
        atr_pct = atr[i] / close[i] * 100 if close[i] > 0 else 0
        high_low_range = (high[i] - low[i]) / close[i-1] * 100 if i >= 1 and close[i-1] > 0 else 0
        std20_pct = std20[i] / close[i] * 100 if close[i] > 0 else 0
        lower_shadow = (close[i] - low[i]) / close[i-1] * 100 if i >= 1 and close[i-1] > 0 else 0
        
        atr_norm = (atr_pct - 3.0) / 1.5
        range_norm = (high_low_range - 2.5) / 1.5
        std_norm = (std20_pct - 3.5) / 1.5
        shadow_norm = (lower_shadow - 1.5) / 1.5
        
        vs[i] = 0.35 * atr_norm + 0.30 * range_norm + 0.20 * std_norm + 0.15 * shadow_norm
    
    return vs


if __name__ == "__main__":
    print(__doc__)
    
    print("\n" + "="*60)
    print("使用示例")
    print("="*60)
    print("""
from volatility_strength import calc_volatility_strength

# 在回测中使用
for i in range(len(signals)):
    if signals[i]:
        vs = calc_volatility_strength(close, high, low, i)
        
        # 过滤低波动信号
        if vs < 0.5:
            continue
        
        # 买入逻辑...
""")
