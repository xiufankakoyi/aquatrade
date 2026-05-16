"""
测试优化后的 LanceDB 性能
========================
"""
import time
import lancedb
import polars as pl
from pathlib import Path

print("=" * 70)
print("LanceDB 优化后性能测试")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n表行数: {table.count_rows():,}")

print("\n=== 索引状态 ===")
try:
    stats = table.index_stats('trade_date_idx')
    print(f"索引类型: {stats.index_type}")
    print(f"索引行数: {stats.num_indexed_rows:,}")
except Exception as e:
    print(f"索引检查: {e}")

print("\n=== 性能测试 ===")

print("\n1. 日期范围查询 (2024-01-01 ~ 2024-12-31):")
t0 = time.perf_counter()
result = table.search().where('trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'').to_arrow()
df = pl.from_arrow(result)
print(f"   {time.perf_counter()-t0:.2f}s, {len(df):,} 行")

print("\n2. 单日查询 (2024-01-02):")
t0 = time.perf_counter()
result = table.search().where('trade_date = date \'2024-01-02\'').to_arrow()
df = pl.from_arrow(result)
print(f"   {time.perf_counter()-t0:.2f}s, {len(df):,} 行")

print("\n3. 全量读取:")
t0 = time.perf_counter()
result = table.to_arrow()
df = pl.from_arrow(result)
print(f"   {time.perf_counter()-t0:.2f}s, {len(df):,} 行")

print("\n4. 单股票查询 (000001.SZ, 2024年):")
t0 = time.perf_counter()
result = table.search().where('stock_code = \'000001.SZ\' AND trade_date >= date \'2024-01-01\' AND trade_date <= date \'2024-12-31\'').to_arrow()
df = pl.from_arrow(result)
print(f"   {time.perf_counter()-t0:.2f}s, {len(df):,} 行")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
