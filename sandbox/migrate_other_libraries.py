"""
迁移 benchmark_daily 和 limit_status 到 ArcticDB
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
print("迁移 benchmark_daily 和 limit_status 到 ArcticDB")
print("=" * 80)

arctic = adb.Arctic("lmdb://./data/arctic_db?map_size=20GB")

for library, file_name in [
    ('benchmark_daily', 'benchmark_daily.parquet'),
    ('limit_status', 'stock_limit_status.parquet')
]:
    print(f"\n{'='*60}")
    print(f"处理: {library}")
    print(f"{'='*60}")
    
    parquet_path = Path(f"./data/parquet_data/{file_name}")
    
    if not parquet_path.exists():
        print(f"文件不存在: {parquet_path}")
        continue
    
    print(f"\n1. 读取 Parquet 文件...")
    t0 = time.perf_counter()
    df = pl.read_parquet(parquet_path)
    elapsed = time.perf_counter() - t0
    print(f"读取耗时: {elapsed:.2f}s")
    print(f"总行数: {len(df)}")
    
    if df.is_empty():
        print("数据为空，跳过")
        continue
    
    print(f"\n2. 检查库...")
    if library not in arctic.list_libraries():
        arctic.create_library(library)
        print(f"创建库: {library}")
    
    lib = arctic[library]
    
    print(f"\n3. 提取年月...")
    if 'trade_date' in df.columns:
        df = df.with_columns(
            pl.col('trade_date').str.slice(0, 7).alias('year_month')
        )
        unique_months = df['year_month'].unique().sort()
        print(f"月份数: {len(unique_months)}")
        
        print(f"\n4. 按月份写入...")
        total_written = 0
        for ym in unique_months:
            t0 = time.perf_counter()
            
            month_df = df.filter(pl.col('year_month') == ym).drop('year_month')
            arrow_table = month_df.to_arrow()
            
            symbol = f"month_{ym.replace('-', '')}"
            lib._nvs.write(symbol, arrow_table)
            
            elapsed = time.perf_counter() - t0
            total_written += len(month_df)
            
            print(f"  {ym}: {len(month_df):>7} 行, {elapsed*1000:>6.1f}ms")
        
        print(f"\n写入完成: {total_written} 行")
    else:
        print("没有 trade_date 列，写入单个符号...")
        t0 = time.perf_counter()
        arrow_table = df.to_arrow()
        lib._nvs.write("all_data", arrow_table)
        elapsed = time.perf_counter() - t0
        print(f"写入耗时: {elapsed:.2f}s")

print("\n" + "=" * 80)
print("迁移完成!")
print("=" * 80)
