"""
测试因子矩阵构建性能
"""
import sys
import time
import pandas as pd
import numpy as np

sys.path.insert(0, '.')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.factor_matrix import FactorMatrixBuilder, FactorMatrixCache

def test_factor_matrix():
    print("=" * 60)
    print("测试因子矩阵构建性能")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2026-01-31"
    
    print(f"\n[1] 加载数据 ({start_date} ~ {end_date})...")
    t0 = time.perf_counter()
    data_query.preload_backtest_data(start_date, end_date)
    preloaded = data_query._preloaded_data
    t1 = time.perf_counter()
    print(f"    数据加载完成: {len(preloaded) if preloaded else 0} 天, 耗时: {(t1-t0):.2f}s")
    
    total_rows = sum(len(df) for df in preloaded.values() if df is not None)
    print(f"    总行数: {total_rows:,}")
    
    print("\n[2] 构建因子矩阵 (无缓存)...")
    builder = FactorMatrixBuilder()
    
    t2 = time.perf_counter()
    matrix = builder.build_from_preloaded(preloaded, use_cache=False)
    t3 = time.perf_counter()
    print(f"    矩阵构建完成: {matrix.values.shape}, 耗时: {(t3-t2):.2f}s")
    
    print("\n[3] 测试缓存保存...")
    cache = FactorMatrixCache()
    cache_key = "test_" + str(int(time.time()))
    
    t4 = time.perf_counter()
    cache.save(cache_key, matrix)
    t5 = time.perf_counter()
    print(f"    缓存保存完成, 耗时: {(t5-t4):.2f}s")
    
    print("\n[4] 测试缓存加载...")
    t6 = time.perf_counter()
    loaded = cache.load(cache_key)
    t7 = time.perf_counter()
    print(f"    缓存加载完成: {loaded.values.shape}, 耗时: {(t7-t6):.2f}s")
    
    print("\n" + "=" * 60)
    print("性能总结:")
    print(f"  数据加载: {(t1-t0):.2f}s")
    print(f"  矩阵构建: {(t3-t2):.2f}s")
    print(f"  缓存保存: {(t5-t4):.2f}s")
    print(f"  缓存加载: {(t7-t6):.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    test_factor_matrix()
