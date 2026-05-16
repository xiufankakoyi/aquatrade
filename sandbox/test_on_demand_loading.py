"""
测试按需加载优化效果

对比：
1. 全列加载 vs 最小列集合加载
2. 内存占用对比
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl
from data_svc.storage.lancedb_reader import get_lancedb_reader, MINIMAL_BACKTEST_COLUMNS, DEFAULT_OHLCV_COLUMNS


def test_column_filtering():
    """测试列过滤加载性能"""
    reader = get_lancedb_reader()
    
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    print("=" * 60)
    print("按需加载优化测试")
    print("=" * 60)
    print(f"日期范围: {start_date} ~ {end_date}")
    print()
    
    all_columns = None
    minimal_columns = MINIMAL_BACKTEST_COLUMNS
    
    print("[1] 全列加载测试...")
    reader.clear_cache()
    t0 = time.perf_counter()
    df_all = reader.read_all_columns(start_date=start_date, end_date=end_date)
    time_all = time.perf_counter() - t0
    mem_all = df_all.estimated_size() / (1024 * 1024)
    cols_all = len(df_all.columns)
    rows_all = len(df_all)
    print(f"   行数: {rows_all:,}")
    print(f"   列数: {cols_all}")
    print(f"   内存: {mem_all:.1f} MB")
    print(f"   耗时: {time_all:.2f}s")
    print(f"   列名: {df_all.columns}")
    print()
    
    print("[2] 最小列集合加载测试...")
    reader.clear_cache()
    t0 = time.perf_counter()
    df_minimal = reader.read_all(start_date, end_date, fields=minimal_columns)
    time_minimal = time.perf_counter() - t0
    mem_minimal = df_minimal.estimated_size() / (1024 * 1024)
    cols_minimal = len(df_minimal.columns)
    rows_minimal = len(df_minimal)
    print(f"   行数: {rows_minimal:,}")
    print(f"   列数: {cols_minimal}")
    print(f"   内存: {mem_minimal:.1f} MB")
    print(f"   耗时: {time_minimal:.2f}s")
    print(f"   列名: {df_minimal.columns}")
    print()
    
    print("=" * 60)
    print("性能对比")
    print("=" * 60)
    if mem_all > 0:
        print(f"内存节省: {mem_all - mem_minimal:.1f} MB ({(1 - mem_minimal/mem_all)*100:.1f}%)")
        print(f"加载加速: {time_all/time_minimal:.2f}x")
        print(f"列数减少: {cols_all - cols_minimal} ({(1 - cols_minimal/cols_all)*100:.1f}%)")
    else:
        print("数据加载失败，无法比较")
    print()
    
    print("最小列集合:")
    print(f"  {MINIMAL_BACKTEST_COLUMNS}")


if __name__ == "__main__":
    test_column_filtering()
