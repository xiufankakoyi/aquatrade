"""
LanceDB 性能优化测试 - 使用 compact_files 和 optimize
======================================================

测试优化后的读取性能
"""
import time
import lancedb
import polars as pl
from pathlib import Path

print("=" * 70)
print("LanceDB 性能优化测试")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n表行数: {table.count_rows():,}")

print("\n=== 检查表状态 ===")
stats = table.stats()
print(f"Stats: {stats}")

print("\n=== 执行优化 ===")

print("\n1. compact_files()...")
t0 = time.perf_counter()
table.compact_files()
print(f"   完成: {time.perf_counter()-t0:.2f}s")

print("\n2. optimize()...")
t0 = time.perf_counter()
table.optimize()
print(f"   完成: {time.perf_counter()-t0:.2f}s")

print("\n=== 检查优化后状态 ===")
stats = table.stats()
print(f"Stats: {stats}")

print("\n=== 性能测试 ===")

print("\n1. 全量读取:")
t0 = time.perf_counter()
arrow = table.to_arrow()
df = pl.from_arrow(arrow)
t1 = time.perf_counter() - t0
print(f"   {t1:.2f}s, {len(df):,} 行")

print("\n2. 日期范围查询 (2024年):")
t0 = time.perf_counter()
result = table.search().where('trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'').to_arrow()
df = pl.from_arrow(result)
t2 = time.perf_counter() - t0
print(f"   {t2:.2f}s, {len(df):,} 行")

print("\n3. 单日查询 (2024-01-02):")
t0 = time.perf_counter()
result = table.search().where('trade_date = date \'2024-01-02\'').to_arrow()
df = pl.from_arrow(result)
t3 = time.perf_counter() - t0
print(f"   {t3:.2f}s, {len(df):,} 行")

print("\n=== Parquet 基准 ===")
parquet_path = Path('data/parquet_data/stock_daily.parquet')

print("\nParquet 全量:")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
t_pq = time.perf_counter() - t0
print(f"   {t_pq:.2f}s")

print("\n=== 汇总 ===")
print(f"{'测试项':<25} {'优化前':<12} {'优化后':<12} {'Parquet':<12}")
print("-" * 60)
print(f"{'全量读取':<25} {'11.38s':<12} {t1:.2f}s{'':<6} {t_pq:.2f}s")
print(f"{'日期范围查询':<25} {'8.38s':<12} {t2:.2f}s{'':<6} {'0.17s':<12}")
print(f"{'单日查询':<25} {'4.06s':<12} {t3:.2f}s{'':<6} {'0.02s':<12}")
