"""
重新迁移数据到 ArcticDB - 按月份分区存储
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
import pyarrow as pa
import arcticdb as adb
from pathlib import Path

print("=" * 80)
print("重新迁移数据到 ArcticDB - 按月份分区存储")
print("=" * 80)

parquet_path = Path("./data/parquet_data/stock_daily.parquet")

print("\n1. 读取 Parquet 文件...")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
elapsed = time.perf_counter() - t0
print(f"读取耗时: {elapsed:.2f}s")
print(f"总行数: {len(df)}")

print("\n2. 提取年月...")
df = df.with_columns(
    pl.col('trade_date').str.slice(0, 7).alias('year_month')
)
unique_months = df['year_month'].unique().sort()
print(f"月份数: {len(unique_months)}")
print(f"月份范围: {unique_months[0]} ~ {unique_months[-1]}")

print("\n3. 连接 ArcticDB...")
arctic = adb.Arctic("lmdb://./data/arctic_db?map_size=20GB")

if 'stock_daily' not in arctic.list_libraries():
    arctic.create_library('stock_daily')
    print("创建 stock_daily 库")

lib = arctic['stock_daily']

print("\n4. 删除旧数据...")
old_symbols = lib.list_symbols()
print(f"旧符号数: {len(old_symbols)}")
for sym in old_symbols:
    try:
        lib.delete(sym)
    except:
        pass
print("删除完成")

print("\n5. 按月份写入...")
total_written = 0
write_times = []

for ym in unique_months:
    t0 = time.perf_counter()
    
    month_df = df.filter(pl.col('year_month') == ym).drop('year_month')
    arrow_table = month_df.to_arrow()
    
    symbol = f"month_{ym.replace('-', '')}"
    lib._nvs.write(symbol, arrow_table)
    
    elapsed = time.perf_counter() - t0
    write_times.append(elapsed)
    total_written += len(month_df)
    
    print(f"  {ym}: {len(month_df):>7} 行, {elapsed*1000:>6.1f}ms")

print(f"\n写入完成: {total_written} 行, 总耗时 {sum(write_times):.2f}s")

print("\n6. 验证读取...")
t0 = time.perf_counter()
all_dfs = []
for ym in unique_months:
    symbol = f"month_{ym.replace('-', '')}"
    try:
        result = lib.read(symbol)
        data = result.data
        if isinstance(data, pa.Table):
            df_read = pl.from_arrow(data)
            all_dfs.append(df_read)
    except Exception as e:
        print(f"  读取 {symbol} 失败: {e}")
elapsed = time.perf_counter() - t0
print(f"读取所有月份: {elapsed:.2f}s")

t0 = time.perf_counter()
combined = pl.concat(all_dfs)
elapsed = time.perf_counter() - t0
print(f"concat: {elapsed*1000:.2f}ms")
print(f"总行数: {len(combined)}")

print("\n7. 测试日期范围读取 (2024-01 ~ 2024-03)...")
t0 = time.perf_counter()
range_dfs = []
for ym in ['202401', '202402', '202403']:
    symbol = f"month_{ym}"
    try:
        result = lib.read(symbol)
        data = result.data
        if isinstance(data, pa.Table):
            df_read = pl.from_arrow(data)
            range_dfs.append(df_read)
    except Exception as e:
        print(f"  读取 {symbol} 失败: {e}")
elapsed = time.perf_counter() - t0
print(f"读取 3 个月: {elapsed*1000:.2f}ms")

if range_dfs:
    combined = pl.concat(range_dfs)
    print(f"行数: {len(combined)}")

print("\n" + "=" * 80)
print("迁移完成!")
print("=" * 80)
