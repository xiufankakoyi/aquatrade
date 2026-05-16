"""
优化 LanceDB 表结构
===================

将 trade_date 从字符串转换为 Date 类型，以便创建索引。
"""
import time
import lancedb
import polars as pl
import pyarrow as pa
from pathlib import Path

print("=" * 70)
print("优化 LanceDB 表结构")
print("=" * 70)

db_path = Path('data/lancedb')
db = lancedb.connect(str(db_path))
table = db.open_table('daily_ohlcv')

print(f"\n当前表行数: {table.count_rows():,}")

print("\n[步骤 1] 读取现有数据...")
t0 = time.perf_counter()
df = pl.from_arrow(table.to_arrow())
print(f"  读取完成: {len(df):,} 行, {time.perf_counter()-t0:.2f}s")

print("\n[步骤 2] 转换日期类型...")
t0 = time.perf_counter()
df = df.with_columns(
    pl.col('trade_date').str.to_date().alias('trade_date')
)
print(f"  转换完成: {time.perf_counter()-t0:.2f}s")
print(f"  新类型: {df.schema['trade_date']}")

print("\n[步骤 3] 删除旧表...")
db.drop_table('daily_ohlcv')

print("\n[步骤 4] 创建新表...")
t0 = time.perf_counter()
new_table = db.create_table('daily_ohlcv', df.to_arrow())
print(f"  创建完成: {time.perf_counter()-t0:.2f}s")

print("\n[步骤 5] 创建索引...")
t0 = time.perf_counter()
new_table.create_scalar_index('trade_date', replace=True)
print(f"  索引创建完成: {time.perf_counter()-t0:.2f}s")

print("\n[步骤 6] 验证索引...")
try:
    stats = new_table.index_stats('trade_date_idx')
    print(f"  索引状态: {stats}")
except Exception as e:
    print(f"  索引检查: {e}")

print("\n[步骤 7] 性能测试...")

print("\n  日期范围查询 (2024-01-01 ~ 2024-12-31):")
t0 = time.perf_counter()
result = new_table.search().where('trade_date >= "2024-01-01" AND trade_date <= "2024-12-31"').to_arrow()
df_result = pl.from_arrow(result)
print(f"    {time.perf_counter()-t0:.2f}s, {len(df_result):,} 行")

print("\n  单日查询 (2024-01-02):")
t0 = time.perf_counter()
result = new_table.search().where('trade_date = "2024-01-02"').to_arrow()
df_result = pl.from_arrow(result)
print(f"    {time.perf_counter()-t0:.2f}s, {len(df_result):,} 行")

print("\n" + "=" * 70)
print("优化完成")
print("=" * 70)
