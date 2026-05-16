"""
重新迁移数据到 ArcticDB - 单符号存储
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
print("重新迁移数据到 ArcticDB - 单符号存储")
print("=" * 80)

parquet_path = Path("./data/parquet_data/stock_daily.parquet")

print("\n1. 读取 Parquet 文件...")
t0 = time.perf_counter()
df = pl.read_parquet(parquet_path)
elapsed = time.perf_counter() - t0
print(f"读取耗时: {elapsed:.2f}s")
print(f"总行数: {len(df)}")
print(f"列数: {len(df.columns)}")

print("\n2. 连接 ArcticDB...")
arctic = adb.Arctic("lmdb://./data/arctic_db")

if 'stock_daily' not in arctic.list_libraries():
    arctic.create_library('stock_daily')
    print("创建 stock_daily 库")

lib = arctic['stock_daily']

print("\n3. 删除旧的分符号数据...")
old_symbols = lib.list_symbols()
print(f"旧符号数: {len(old_symbols)}")

for sym in old_symbols:
    try:
        lib.delete(sym)
    except:
        pass
print("删除完成")

print("\n4. 写入单符号数据...")
t0 = time.perf_counter()
arrow_table = df.to_arrow()
lib._nvs.write("all_stocks", arrow_table)
elapsed = time.perf_counter() - t0
print(f"写入耗时: {elapsed:.2f}s")

print("\n5. 验证读取...")
t0 = time.perf_counter()
result = lib.read("all_stocks")
data = result.data
elapsed = time.perf_counter() - t0
print(f"读取耗时: {elapsed*1000:.2f}ms")
print(f"数据类型: {type(data)}")
print(f"行数: {len(data)}")

if isinstance(data, pa.Table):
    df_read = pl.from_arrow(data)
    print(f"Polars 转换后行数: {len(df_read)}")
    
    print("\n6. 测试日期过滤...")
    t0 = time.perf_counter()
    filtered = df_read.filter(
        (pl.col('trade_date') >= '2024-01-01') & 
        (pl.col('trade_date') <= '2024-03-31')
    )
    elapsed = time.perf_counter() - t0
    print(f"过滤耗时: {elapsed*1000:.2f}ms")
    print(f"过滤后行数: {len(filtered)}")

print("\n" + "=" * 80)
print("迁移完成!")
print("=" * 80)
