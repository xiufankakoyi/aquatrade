"""分析 Polars 加载器的性能瓶颈"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
import polars as pl
from pathlib import Path
import numpy as np

def profile_polars_loading():
    """分析 Polars 加载的各个阶段"""
    print("\n" + "=" * 70)
    print("Polars 加载性能分析")
    print("=" * 70)
    
    parquet_dir = Path("data/parquet_data")
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    # 1. 测试 scan_parquet 的 filter pushdown 性能
    print("\n--- 1. scan_parquet + filter ---")
    t_start = time.perf_counter()
    
    daily_path = parquet_dir / "stock_daily.parquet"
    lf = pl.scan_parquet(daily_path)
    lf = lf.filter(
        (pl.col('trade_date') >= start_date) &
        (pl.col('trade_date') <= end_date) &
        (pl.col('volume') > 0)
    )
    lf = lf.select(['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume'])
    df = lf.collect()
    
    t_end = time.perf_counter()
    print(f"  耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"  行数: {len(df)}")
    
    # 2. 测试 read_parquet 的性能
    print("\n--- 2. read_parquet (无过滤) ---")
    t_start = time.perf_counter()
    
    df_full = pl.read_parquet(daily_path)
    
    t_end = time.perf_counter()
    print(f"  耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"  总行数: {len(df_full)}")
    
    # 3. 测试内存映射读取
    print("\n--- 3. read_parquet (使用内存映射) ---")
    t_start = time.perf_counter()
    
    df_mmap = pl.read_parquet(daily_path, memory_map=True)
    
    t_end = time.perf_counter()
    print(f"  耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"  总行数: {len(df_mmap)}")
    
    # 4. 测试 PyArrow 后端
    print("\n--- 4. 使用 PyArrow 读取 ---")
    t_start = time.perf_counter()
    
    import pyarrow.parquet as pq
    table = pq.read_table(daily_path)
    df_arrow = pl.from_arrow(table)
    
    t_end = time.perf_counter()
    print(f"  耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"  总行数: {len(df_arrow)}")
    
    # 5. 测试过滤性能
    print("\n--- 5. DataFrame 过滤性能 ---")
    t_start = time.perf_counter()
    
    df_filtered = df_full.filter(
        (pl.col('trade_date') >= start_date) &
        (pl.col('trade_date') <= end_date) &
        (pl.col('volume') > 0)
    )
    
    t_end = time.perf_counter()
    print(f"  耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"  过滤后行数: {len(df_filtered)}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    profile_polars_loading()
