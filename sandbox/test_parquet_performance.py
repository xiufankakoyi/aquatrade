"""
测试 Parquet 读取性能优化
"""
import time
import polars as pl
from pathlib import Path

parquet_file = Path('data/parquet_data/stock_limit_status.parquet')
parquet_path = str(parquet_file.resolve()).replace('\\', '/')

start_str, end_str = '2024-04-01', '2024-05-25'

print("=== 测试 1: 原始方式（全表读取 + filter）===")
start = time.perf_counter()
df = pl.scan_parquet(parquet_path).collect()
result = df.filter((pl.col('trade_date') >= start_str) & (pl.col('trade_date') <= end_str))
print(f"  读取+切片: {time.perf_counter() - start:.3f}s, 行数: {len(result)}")

print("\n=== 测试 2: 使用 Lazy API 下推过滤 ===")
start = time.perf_counter()
result = (pl.scan_parquet(parquet_path)
    .filter((pl.col('trade_date') >= start_str) & (pl.col('trade_date') <= end_str))
    .select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
    .collect())
print(f"  查询: {time.perf_counter() - start:.3f}s, 行数: {len(result)}")

print("\n=== 测试 3: 使用并行读取 ===")
start = time.perf_counter()
result = (pl.scan_parquet(parquet_path, parallel='columns')
    .filter((pl.col('trade_date') >= start_str) & (pl.col('trade_date') <= end_str))
    .select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
    .collect())
print(f"  查询(parallel='columns'): {time.perf_counter() - start:.3f}s, 行数: {len(result)}")

print("\n=== 测试 4: 使用行组过滤 ===")
start = time.perf_counter()
scan = pl.scan_parquet(parquet_path)
result = (scan
    .filter((pl.col('trade_date') >= start_str) & (pl.col('trade_date') <= end_str))
    .select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
    .collect())
print(f"  查询: {time.perf_counter() - start:.3f}s, 行数: {len(result)}")

print("\n=== 测试 5: 转换为 Pandas 的时间 ===")
start = time.perf_counter()
pdf = result.to_pandas()
print(f"  to_pandas: {time.perf_counter() - start:.3f}s")
