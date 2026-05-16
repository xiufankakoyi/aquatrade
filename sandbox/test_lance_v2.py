"""
LanceDB 性能优化测试 v2
=======================

尝试不同的读取策略：
1. 使用 scanner() 惰性求值
2. 使用 Polars LazyFrame
3. 分批读取
"""
import time
import lancedb
import polars as pl
import pyarrow as pa
from pathlib import Path

print("=" * 70)
print("LanceDB 性能优化测试 v2")
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
print(f"  耗时: {t1:.2f}s")

print("\n方法 2: search().where() + limit")
t0 = time.perf_counter()
total = table.count_rows()
batch_size = 1_000_000
all_dfs = []
for offset in range(0, total, batch_size):
    result = table.search().limit(batch_size).offset(offset).to_arrow()
    df_batch = pl.from_arrow(result)
    all_dfs.append(df_batch)
df = pl.concat(all_dfs)
t2 = time.perf_counter() - t0
print(f"  耗时: {t2:.2f}s")

print("\n方法 3: 使用 PyArrow Dataset")
t0 = time.perf_counter()
import pyarrow.dataset as ds
lance_path = db_path / 'daily_ohlcv.lance'
try:
    dataset = ds.dataset(str(lance_path), format='lance')
    table_arrow = dataset.to_table()
    df = pl.from_arrow(table_arrow)
    t3 = time.perf_counter() - t0
    print(f"  耗时: {t3:.2f}s")
except Exception as e:
    print(f"  失败: {e}")
    t3 = None

print("\n方法 4: Polars scan_parquet (基准)")
parquet_path = Path('data/parquet_data/stock_daily.parquet')
t0 = time.perf_counter()
df = pl.scan_parquet(parquet_path).collect()
t4 = time.perf_counter() - t0
print(f"  耗时: {t4:.2f}s")

print("\n=== 日期范围查询对比 ===")

print("\nLanceDB search().where():")
t0 = time.perf_counter()
result = table.search().where('trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'').to_arrow()
df = pl.from_arrow(result)
t_lance = time.perf_counter() - t0
print(f"  耗时: {t_lance:.2f}s, {len(df):,} 行")

print("\nParquet + Polars filter:")
t0 = time.perf_counter()
df = pl.scan_parquet(parquet_path).filter(
    (pl.col('trade_date') >= '2024-01-01') & (pl.col('trade_date') <= '2024-12-31')
).collect()
t_pq = time.perf_counter() - t0
print(f"  耗时: {t_pq:.2f}s, {len(df):,} 行")

print("\n=== 汇总 ===")
print(f"{'方法':<30} {'耗时':<10}")
print("-" * 40)
print(f"{'LanceDB to_arrow()':<30} {t1:.2f}s")
print(f"{'LanceDB 分批读取':<30} {t2:.2f}s")
if t3:
    print(f"{'PyArrow Dataset':<30} {t3:.2f}s")
print(f"{'Parquet (基准)':<30} {t4:.2f}s")
print(f"{'LanceDB 日期查询':<30} {t_lance:.2f}s")
print(f"{'Parquet 日期查询':<30} {t_pq:.2f}s")
