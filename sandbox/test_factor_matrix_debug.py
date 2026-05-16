"""
诊断因子矩阵问题
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

import polars as pl


def test_factor_matrix():
    """测试因子矩阵"""
    print("\n" + "=" * 80)
    print("诊断因子矩阵问题")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    print("\n[1] 初始化并预加载数据...")
    manager = get_unified_manager()
    preloaded = manager.preload_to_memory(start_date="2024-01-01", end_date="2025-12-31")
    
    print(f"缓存状态: cache_loaded={manager._cache_loaded}, range={manager._preloaded_date_range}")
    
    print("\n[2] 构建因子矩阵...")
    from core.backtest.factor_matrix import build_factor_matrix
    
    t0 = time.perf_counter()
    factor_matrix = build_factor_matrix(preloaded)
    elapsed = time.perf_counter() - t0
    
    print(f"因子矩阵构建耗时: {elapsed:.2f}s")
    print(f"T={len(factor_matrix.dates)}, N={len(factor_matrix.codes_str)}, F={len(factor_matrix.factor_names)}")
    print(f"dates 前5个: {factor_matrix.dates[:5]}")
    print(f"dates 后5个: {factor_matrix.dates[-5:]}")
    print(f"date_to_idx 样例: {list(factor_matrix.date_to_idx.items())[:5]}")
    
    print("\n[3] 测试日期查找...")
    test_dates = ['2024-01-02', '2024-01-03', '2025-12-30', '2025-12-31']
    for date in test_dates:
        idx = factor_matrix.date_to_idx.get(date, -1)
        print(f"  {date}: idx={idx}")
    
    print("\n[4] 测试矩阵切片...")
    date_str = '2024-01-02'
    date_idx = factor_matrix.date_to_idx.get(date_str, -1)
    if date_idx >= 0:
        factor_slice = factor_matrix.values[date_idx, :, :]
        print(f"factor_slice shape: {factor_slice.shape}")
        print(f"factor_slice 前3行: {factor_slice[:3, :5]}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_factor_matrix()
