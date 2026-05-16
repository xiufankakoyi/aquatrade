"""
LanceDB 性能优化测试 v4 - 尝试不同的读取方式
============================================

测试不同的读取方式，找到最快的方案
"""
import time
import lancedb
import polars as pl
import pyarrow as pa
from pathlib import Path

print("=" * 70)
print("LanceDB 性能优化测试 v4")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n表行数: {table.count_rows():,}")

print("\n=== 方法对比 ===")

print("\n方法 1: to_arrow() 直接读取")
t0 = time.perf_counter()
arrow = table.to_arrow()
df = pl.from_arrow(arrow)
t1 = time.perf_counter() - t0
print(f"   {t1:.2f}s, {len(df):,} 行")

print("\n方法 2: to_polars() 直接读取")
t0 = time.perf_counter()
df = table.to_polars()
if hasattr(df, 'collect'):
    df = df.collect()
t2 = time.perf_counter() - t0
print(f"   {t2:.2f}s, {len(df):,} 行")

print("\n方法 3: search().to_arrow()")
t0 = time.perf_counter()
arrow = table.search().to_arrow()
df = pl.from_arrow(arrow)
t3 = time.perf_counter() - t0
print(f"   {t3:.2f}s, {len(df):,} 行")

print("\n方法 4: search().limit() 分批读取")
t0 = time.perf_counter()
batch_size = 2_000_000
total = table.count_rows()
all_dfs = []
for offset in range(0, total, batch_size):
    result = table.search().limit(batch_size).offset(offset).to_arrow()
    df_batch = pl.from_arrow(result)
    all_dfs.append(df_batch)
df = pl.concat(all_dfs)
t4 = time.perf_counter() - t0
print(f"   {t4:.2f}s, {len(df):,} 行")

print("\n方法 5: to_lance() + PyArrow Dataset")
t0 = time.perf_counter()
try:
    lance_ds = table.to_lance()
    arrow = lance_ds.to_table()
    df = pl.from_arrow(arrow)
    t5 = time.perf_counter() - t0
    print(f"   {t5:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"   失败: {e}")
    t5 = None

print("\n方法 6: to_lance() + scanner")
t0 = time.perf_counter()
try:
    lance_ds = table.to_lance()
    scanner = lance_ds.scanner()
    arrow = scanner.to_table()
    df = pl.from_arrow(arrow)
    t6 = time.perf_counter() - t0
    print(f"   {t6:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"   失败: {e}")
    t6 = None

print("\n方法 7: to_lance() + filter")
t0 = time.perf_counter()
try:
    lance_ds = table.to_lance()
    scanner = lance_ds.scanner(filter="trade_date >= date '2024-01-01' AND trade_date <= date '2024-12-31'")
    arrow = scanner.to_table()
    df = pl.from_arrow(arrow)
    t7 = time.perf_counter() - t0
    print(f"   {t7:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"   失败: {e}")
    t7 = None

print("\n=== Parquet 基准 ===")
parquet_path = Path('data/parquet_data/stock_daily.parquet')

print("\nParquet 全量:")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
t_pq = time.perf_counter() - t0
print(f"   {t_pq:.2f}s")

print("\n=== 汇总 ===")
print(f"{'方法':<30} {'耗时':<10}")
print("-" * 40)
print(f"{'to_arrow()':<30} {t1:.2f}s")
print(f"{'to_polars()':<30} {t2:.2f}s")
print(f"{'search().to_arrow()':<30} {t3:.2f}s")
print(f"{'search().limit() 分批':<30} {t4:.2f}s")
if t5:
    print(f"{'to_lance() + to_table()':<30} {t5:.2f}s")
if t6:
    print(f"{'to_lance() + scanner':<30} {t6:.2f}s")
if t7:
    print(f"{'to_lance() + filter':<30} {t7:.2f}s")
print(f"{'Parquet (基准)':<30} {t_pq:.2f}s")
