import time
import polars as pl
from pathlib import Path

LANCE_DIR = Path('data/test_lancedb_optimized')

print('=== LanceDB 各种读取方式对比 ===')

import lancedb
db = lancedb.connect(str(LANCE_DIR))
table = db.open_table('stock_daily')

print('\n1. to_arrow():')
t0 = time.perf_counter()
df = pl.from_arrow(table.to_arrow())
print(f'   {time.perf_counter()-t0:.2f}s')

print('\n2. to_pandas():')
t0 = time.perf_counter()
df = pl.from_pandas(table.to_pandas())
print(f'   {time.perf_counter()-t0:.2f}s')

print('\n3. head() [前1000行]:')
t0 = time.perf_counter()
result = table.head(1000)
print(f'   {time.perf_counter()-t0:.2f}s')

print('\n4. 过滤查询:')
t0 = time.perf_counter()
result = table.search().where('trade_date = "2024-01-02"').to_arrow()
print(f'   {time.perf_counter()-t0:.2f}s')

print('\n5. count_rows():')
t0 = time.perf_counter()
cnt = table.count_rows()
print(f'   {time.perf_counter()-t0:.2f}s, {cnt:,} 行')

print('\n=== Parquet 基准 ===')
t0 = time.perf_counter()
df = pl.read_parquet('data/parquet_data/stock_daily.parquet')
print(f'Parquet: {time.perf_counter()-t0:.2f}s')
