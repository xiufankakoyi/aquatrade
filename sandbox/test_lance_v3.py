"""
LanceDB 性能优化测试 v3
=======================

使用 scanner() 方法，它返回 PyArrow Dataset，可能更高效。
"""
import time
import lancedb
import polars as pl
import pyarrow as pa
from pathlib import Path

print("=" * 70)
print("LanceDB 性能优化测试 v3 - 使用 scanner()")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n表行数: {table.count_rows():,}")

print("\n=== 方法对比 ===")

print("\n方法 1: table.scanner() + to_table()")
t0 = time.perf_counter()
try:
    scanner = table.scanner()
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    t1 = time.perf_counter() - t0
    print(f"  耗时: {t1:.2f}s")
except Exception as e:
    print(f"  失败: {e}")
    t1 = None

print("\n方法 2: table.scanner() + filter")
t0 = time.perf_counter()
try:
    scanner = table.scanner(filter='trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'')
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    t2 = time.perf_counter() - t0
    print(f"  耗时: {t2:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"  失败: {e}")
    t2 = None

print("\n方法 3: table.scanner() + columns")
t0 = time.perf_counter()
try:
    scanner = table.scanner(columns=['stock_code', 'trade_date', 'close', 'volume'])
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    t3 = time.perf_counter() - t0
    print(f"  耗时: {t3:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"  失败: {e}")
    t3 = None

print("\n方法 4: table.scanner() + batch_size")
t0 = time.perf_counter()
try:
    scanner = table.scanner(batch_size=100000)
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    t4 = time.perf_counter() - t0
    print(f"  耗时: {t4:.2f}s")
except Exception as e:
    print(f"  失败: {e}")
    t4 = None

print("\n方法 5: table.scanner() + filter + columns")
t0 = time.perf_counter()
try:
    scanner = table.scanner(
        filter='trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'',
        columns=['stock_code', 'trade_date', 'close', 'volume']
    )
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    t5 = time.perf_counter() - t0
    print(f"  耗时: {t5:.2f}s, {len(df):,} 行")
except Exception as e:
    print(f"  失败: {e}")
    t5 = None

print("\n=== Parquet 基准 ===")
parquet_path = Path('data/parquet_data/stock_daily.parquet')

print("\nParquet 全量读取:")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
t_pq_full = time.perf_counter() - t0
print(f"  耗时: {t_pq_full:.2f}s")

print("\nParquet 日期过滤:")
t0 = time.perf_counter()
df = pl.scan_parquet(parquet_path).filter(
    (pl.col('trade_date') >= '2024-01-01') & (pl.col('trade_date') <= '2024-12-31')
).collect()
t_pq_filter = time.perf_counter() - t0
print(f"  耗时: {t_pq_filter:.2f}s, {len(df):,} 行")

print("\n=== 汇总 ===")
print(f"{'方法':<40} {'耗时':<10}")
print("-" * 50)
if t1:
    print(f"{'LanceDB scanner() 全量':<40} {t1:.2f}s")
if t2:
    print(f"{'LanceDB scanner() + filter':<40} {t2:.2f}s")
if t3:
    print(f"{'LanceDB scanner() + columns':<40} {t3:.2f}s")
if t4:
    print(f"{'LanceDB scanner() + batch_size':<40} {t4:.2f}s")
if t5:
    print(f"{'LanceDB scanner() + filter + columns':<40} {t5:.2f}s")
print(f"{'Parquet 全量':<40} {t_pq_full:.2f}s")
print(f"{'Parquet 日期过滤':<40} {t_pq_filter:.2f}s")
