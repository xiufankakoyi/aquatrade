"""
LanceDB 性能优化测试 v5 - 深入优化
==================================

基于 to_lance() + scanner 的发现，继续优化
"""
import time
import lancedb
import polars as pl
import pyarrow as pa
from pathlib import Path

print("=" * 70)
print("LanceDB 性能优化测试 v5 - 深入优化")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n表行数: {table.count_rows():,}")

lance_ds = table.to_lance()

print("\n=== 方法对比 ===")

print("\n方法 1: scanner() 默认")
t0 = time.perf_counter()
scanner = lance_ds.scanner()
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t1 = time.perf_counter() - t0
print(f"   {t1:.2f}s, {len(df):,} 行")

print("\n方法 2: scanner(batch_size=1M)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(batch_size=1_000_000)
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t2 = time.perf_counter() - t0
print(f"   {t2:.2f}s, {len(df):,} 行")

print("\n方法 3: scanner(batch_size=10M)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(batch_size=10_000_000)
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t3 = time.perf_counter() - t0
print(f"   {t3:.2f}s, {len(df):,} 行")

print("\n方法 4: scanner(columns=OHLCV)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume'])
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t4 = time.perf_counter() - t0
print(f"   {t4:.2f}s, {len(df):,} 行")

print("\n方法 5: scanner + filter (2024年)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(filter="trade_date >= date '2024-01-01' AND trade_date <= date '2024-12-31'")
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t5 = time.perf_counter() - t0
print(f"   {t5:.2f}s, {len(df):,} 行")

print("\n方法 6: scanner + filter + columns")
t0 = time.perf_counter()
scanner = lance_ds.scanner(
    filter="trade_date >= date '2024-01-01' AND trade_date <= date '2024-12-31'",
    columns=['stock_code', 'trade_date', 'close', 'volume']
)
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t6 = time.perf_counter() - t0
print(f"   {t6:.2f}s, {len(df):,} 行")

print("\n方法 7: scanner + filter (单日)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(filter="trade_date = date '2024-01-02'")
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t7 = time.perf_counter() - t0
print(f"   {t7:.2f}s, {len(df):,} 行")

print("\n方法 8: scanner + filter + columns (单日)")
t0 = time.perf_counter()
scanner = lance_ds.scanner(
    filter="trade_date = date '2024-01-02'",
    columns=['stock_code', 'trade_date', 'close', 'volume']
)
arrow = scanner.to_table()
df = pl.from_arrow(arrow)
t8 = time.perf_counter() - t0
print(f"   {t8:.2f}s, {len(df):,} 行")

print("\n=== Parquet 基准 ===")
parquet_path = Path('data/parquet_data/stock_daily.parquet')

print("\nParquet 全量:")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
t_pq_full = time.perf_counter() - t0
print(f"   {t_pq_full:.2f}s")

print("\nParquet 2024年:")
t0 = time.perf_counter()
df = pl.scan_parquet(parquet_path).filter(
    (pl.col('trade_date') >= '2024-01-01') & (pl.col('trade_date') <= '2024-12-31')
).collect()
t_pq_2024 = time.perf_counter() - t0
print(f"   {t_pq_2024:.2f}s, {len(df):,} 行")

print("\n=== 汇总 ===")
print(f"{'方法':<35} {'耗时':<10}")
print("-" * 45)
print(f"{'scanner() 默认':<35} {t1:.2f}s")
print(f"{'scanner(batch_size=1M)':<35} {t2:.2f}s")
print(f"{'scanner(batch_size=10M)':<35} {t3:.2f}s")
print(f"{'scanner(columns=OHLCV)':<35} {t4:.2f}s")
print(f"{'scanner + filter (2024年)':<35} {t5:.2f}s")
print(f"{'scanner + filter + cols (2024年)':<35} {t6:.2f}s")
print(f"{'scanner + filter (单日)':<35} {t7:.2f}s")
print(f"{'scanner + filter + cols (单日)':<35} {t8:.2f}s")
print(f"{'Parquet 全量':<35} {t_pq_full:.2f}s")
print(f"{'Parquet 2024年':<35} {t_pq_2024:.2f}s")

print("\n=== 目标达成情况 ===")
if t3 < 5:
    print(f"✅ 全量读取达到目标: {t3:.2f}s < 5s")
else:
    print(f"❌ 全量读取未达目标: {t3:.2f}s >= 5s")

if t5 < 5:
    print(f"✅ 日期范围查询达到目标: {t5:.2f}s < 5s")
else:
    print(f"❌ 日期范围查询未达目标: {t5:.2f}s >= 5s")
