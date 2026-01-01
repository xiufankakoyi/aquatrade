"""
高性能向量化计算函数 - 使用 Numba JIT 加速

所有函数接收 (T, N) 形状的 NumPy 数组，输出也是 (T, N)
T: 时间维度（交易日数）
N: 股票数量
"""
import numpy as np

try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # 降级：如果没有 Numba，使用普通装饰器
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@jit(nopython=True, cache=True, fastmath=True)
def calc_ma_vectorized(matrix: np.ndarray, window: int) -> np.ndarray:
    """
    计算移动平均线（使用 cumsum 优化，处理 NaN）
    
    参数:
        matrix: (T, N) 形状的 NumPy 数组，输入数据
        window: 移动平均窗口大小
    
    返回:
        ma_matrix: (T, N) 形状的 NumPy 数组，移动平均结果
                   - 前 window-1 行为 NaN
                   - 后续行为有效的移动平均值
    
    算法:
        使用累积和 (cumsum) 优化，避免重复计算窗口和
        时间复杂度: O(T*N)，空间复杂度: O(T*N)
    """
    T, N = matrix.shape
    
    # 初始化输出数组
    ma_matrix = np.full((T, N), np.nan, dtype=np.float64)
    
    # 如果窗口大于等于时间长度，直接返回全 NaN
    if window > T or window < 1:
        return ma_matrix
    
    # 计算累积和（处理 NaN）
    # 将 NaN 视为 0，同时记录有效计数
    cumsum = np.zeros((T, N), dtype=np.float64)
    cumcount = np.zeros((T, N), dtype=np.int32)
    
    # 第一行单独处理
    for n in range(N):
        val = matrix[0, n]
        if not np.isnan(val):
            cumsum[0, n] = val
            cumcount[0, n] = 1
    
    # 累积计算
    for t in range(1, T):
        for n in range(N):
            val = matrix[t, n]
            if not np.isnan(val):
                cumsum[t, n] = cumsum[t-1, n] + val
                cumcount[t, n] = cumcount[t-1, n] + 1
            else:
                cumsum[t, n] = cumsum[t-1, n]
                cumcount[t, n] = cumcount[t-1, n]
    
    # 计算移动平均
    for t in range(window - 1, T):
        prev_idx = t - window
        for n in range(N):
            if prev_idx >= 0:
                # 窗口和 = 当前累积和 - 窗口前的累积和
                window_sum = cumsum[t, n] - cumsum[prev_idx, n]
                window_count = cumcount[t, n] - cumcount[prev_idx, n]
            else:
                # 窗口前没有数据，直接用当前累积值
                window_sum = cumsum[t, n]
                window_count = cumcount[t, n]
            
            # 计算平均值（如果有有效数据）
            if window_count > 0:
                ma_matrix[t, n] = window_sum / window_count
    
    return ma_matrix


@jit(nopython=True, cache=True, fastmath=True)
def calc_cross_over(fast_line: np.ndarray, slow_line: np.ndarray) -> np.ndarray:
    """
    计算金叉（快线上穿慢线）
    
    参数:
        fast_line: (T, N) 形状的 NumPy 数组，快线数据
        slow_line: (T, N) 形状的 NumPy 数组，慢线数据
    
    返回:
        cross_over_matrix: (T, N) 形状的 NumPy 数组，布尔类型
                          - True 表示该位置发生金叉（快线上穿慢线）
                          - False 表示未发生金叉
    
    金叉定义:
        当前时刻: fast_line[t] > slow_line[t]
        前一时刻: fast_line[t-1] <= slow_line[t-1]
        即：快线从下方穿越到上方
    """
    T, N = fast_line.shape
    cross_over_matrix = np.zeros((T, N), dtype=np.bool_)
    
    # 第一行无法判断金叉（需要前一行数据）
    for t in range(1, T):
        for n in range(N):
            fast_curr = fast_line[t, n]
            fast_prev = fast_line[t-1, n]
            slow_curr = slow_line[t, n]
            slow_prev = slow_line[t-1, n]
            
            # 检查是否有 NaN
            if (np.isnan(fast_curr) or np.isnan(fast_prev) or 
                np.isnan(slow_curr) or np.isnan(slow_prev)):
                cross_over_matrix[t, n] = False
                continue
            
            # 金叉条件：当前快线 > 慢线，且前一刻快线 <= 慢线
            if (fast_curr > slow_curr) and (fast_prev <= slow_prev):
                cross_over_matrix[t, n] = True
            else:
                cross_over_matrix[t, n] = False
    
    return cross_over_matrix


@jit(nopython=True, cache=True, fastmath=True)
def calc_cross_under(fast_line: np.ndarray, slow_line: np.ndarray) -> np.ndarray:
    """
    计算死叉（快线下穿慢线）
    
    参数:
        fast_line: (T, N) 形状的 NumPy 数组，快线数据
        slow_line: (T, N) 形状的 NumPy 数组，慢线数据
    
    返回:
        cross_under_matrix: (T, N) 形状的 NumPy 数组，布尔类型
                           - True 表示该位置发生死叉（快线下穿慢线）
                           - False 表示未发生死叉
    
    死叉定义:
        当前时刻: fast_line[t] < slow_line[t]
        前一时刻: fast_line[t-1] >= slow_line[t-1]
        即：快线从上方穿越到下方
    """
    T, N = fast_line.shape
    cross_under_matrix = np.zeros((T, N), dtype=np.bool_)
    
    # 第一行无法判断死叉（需要前一行数据）
    for t in range(1, T):
        for n in range(N):
            fast_curr = fast_line[t, n]
            fast_prev = fast_line[t-1, n]
            slow_curr = slow_line[t, n]
            slow_prev = slow_line[t-1, n]
            
            # 检查是否有 NaN
            if (np.isnan(fast_curr) or np.isnan(fast_prev) or 
                np.isnan(slow_curr) or np.isnan(slow_prev)):
                cross_under_matrix[t, n] = False
                continue
            
            # 死叉条件：当前快线 < 慢线，且前一刻快线 >= 慢线
            if (fast_curr < slow_curr) and (fast_prev >= slow_prev):
                cross_under_matrix[t, n] = True
            else:
                cross_under_matrix[t, n] = False
    
    return cross_under_matrix

