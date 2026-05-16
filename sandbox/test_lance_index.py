import time
import lancedb
import polars as pl
from pathlib import Path

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print('=== 检查索引状态 ===')
print(f'表行数: {table.count_rows():,}')

print('\n=== 测试不同查询方式 ===')

print('\n1. search().where() + to_arrow():')
t0 = time.perf_counter()
result = table.search().where('trade_date >= "2024-01-01" AND trade_date <= "2024-12-31"').to_arrow()
df = pl.from_arrow(result)
print(f'   {time.perf_counter()-t0:.2f}s, {len(df):,} 行')

print('\n2. to_arrow() + Polars 过滤:')
t0 = time.perf_counter()
arrow = table.to_arrow()
df = pl.from_arrow(arrow)
df = df.filter((pl.col('trade_date') >= '2024-01-01') & (pl.col('trade_date') <= '2024-12-31'))
print(f'   {time.perf_counter()-t0:.2f}s, {len(df):,} 行')

print('\n3. 检查索引:')
try:
    stats = table.index_stats('trade_date_idx')
    print(f'   索引状态: {stats}')
except Exception as e:
    print(f'   索引检查失败: {e}')

print('\n4. 尝试创建索引:')
try:
    table.create_scalar_index('trade_date', replace=True)
    print('   索引创建成功')
except Exception as e:
    print(f'   索引创建失败: {e}')

print('\n5. 再次测试 search().where():')
t0 = time.perf_counter()
result = table.search().where('trade_date >= "2024-01-01" AND trade_date <= "2024-12-31"').to_arrow()
df = pl.from_arrow(result)
print(f'   {time.perf_counter()-t0:.2f}s, {len(df):,} 行')
