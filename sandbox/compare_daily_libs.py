"""
对比 stock_daily 和 daily 两个库的数据差异
"""
from pathlib import Path
from arcticdb import Arctic
import pandas as pd

base_path = Path('data/arctic_db')

# 连接两个库
stock_daily_path = base_path / 'stock_daily'
daily_path = base_path / 'daily'

arctic_stock = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')
arctic_daily = Arctic(f'lmdb://{daily_path}?map_size=10GB')

stock_lib = arctic_stock['stock_daily']
daily_lib = arctic_daily['daily']

stock_symbols = set(stock_lib.list_symbols())
daily_symbols = set(daily_lib.list_symbols())

print("=" * 60)
print("股票数量对比")
print("=" * 60)
print(f"stock_daily: {len(stock_symbols)} 只")
print(f"daily:       {len(daily_symbols)} 只")

# 差异
only_in_stock = stock_symbols - daily_symbols
only_in_daily = daily_symbols - stock_symbols

print(f"\n仅在 stock_daily: {len(only_in_stock)} 只")
print(f"仅在 daily:       {len(only_in_daily)} 只")

if only_in_stock:
    print(f"仅在 stock_daily 的股票: {list(only_in_stock)[:10]}...")
if only_in_daily:
    print(f"仅在 daily 的股票: {list(only_in_daily)[:10]}...")

print("\n" + "=" * 60)
print("抽样对比数据完整性 (前10只共有股票)")
print("=" * 60)

common = list(stock_symbols & daily_symbols)[:10]
total_rows_stock = 0
total_rows_daily = 0
min_dates_stock = {}
min_dates_daily = {}
max_dates_stock = {}
max_dates_daily = {}

for s in common:
    item_stock = stock_lib.read(s)
    df_stock = item_stock.data
    
    item_daily = daily_lib.read(s)
    df_daily = item_daily.data
    
    total_rows_stock += len(df_stock)
    total_rows_daily += len(df_daily)
    
    min_dates_stock[s] = df_stock.index.min()
    max_dates_stock[s] = df_stock.index.max()
    min_dates_daily[s] = df_daily.index.min()
    max_dates_daily[s] = df_daily.index.max()
    
    diff = len(df_stock) - len(df_daily)
    print(f"{s}: stock_daily={len(df_stock)}行, daily={len(df_daily)}行, 差={diff}")

print(f"\n总行数: stock_daily={total_rows_stock}, daily={total_rows_daily}")

# 检查日期范围差异
print("\n" + "=" * 60)
print("日期范围对比")
print("=" * 60)
for s in common[:5]:
    print(f"{s}:")
    print(f"  stock_daily: {min_dates_stock[s]} ~ {max_dates_stock[s]}")
    print(f"  daily:       {min_dates_daily[s]} ~ {max_dates_daily[s]}")
