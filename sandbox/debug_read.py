"""
调试 UnifiedDataManager 读取
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import arcticdb as adb
import polars as pl
import pyarrow as pa

print("=" * 80)
print("调试 UnifiedDataManager 读取")
print("=" * 80)

arctic = adb.Arctic("lmdb://./data/arctic_db?map_size=20GB")
lib = arctic['stock_daily']

start_date = '2024-01-01'
end_date = '2024-03-31'

print("\n1. 获取所有符号...")
all_symbols = lib.list_symbols()
print(f"符号数: {len(all_symbols)}")

print("\n2. 计算需要的月份...")
start_year = int(start_date[:4])
start_month = int(start_date[5:7])
end_year = int(end_date[:4])
end_month = int(end_date[5:7])

needed_months = []
y, m = start_year, start_month
while (y, m) <= (end_year, end_month):
    needed_months.append(f"month_{y}{m:02d}")
    m += 1
    if m > 12:
        m = 1
        y += 1

print(f"需要的月份: {needed_months}")

print("\n3. 过滤符号...")
symbols = [s for s in all_symbols if s in needed_months]
print(f"匹配的符号: {symbols}")

print("\n4. 读取每个符号...")
all_dfs = []
for sym in symbols:
    try:
        result = lib.read(sym)
        data = result.data
        
        if isinstance(data, pa.Table):
            df = pl.from_arrow(data)
        else:
            df = pl.from_pandas(data)
        
        print(f"  {sym}: {len(df)} 行 (原始)")
        
        if start_date and 'trade_date' in df.columns:
            df = df.filter(pl.col('trade_date') >= start_date)
        if end_date and 'trade_date' in df.columns:
            df = df.filter(pl.col('trade_date') <= end_date)
        
        print(f"  {sym}: {len(df)} 行 (过滤后)")
        
        if not df.is_empty():
            all_dfs.append(df)
    except Exception as e:
        print(f"  {sym}: 读取失败 - {e}")
        import traceback
        traceback.print_exc()

print("\n5. 合并数据...")
if all_dfs:
    df = pl.concat(all_dfs)
    print(f"总行数: {len(df)}")
else:
    print("没有数据!")
