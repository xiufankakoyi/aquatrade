"""
检查复权因子
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("检查复权因子")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    pl.col('stock_code') == '000001'
).select(['trade_date', 'open', 'close', 'adj_factor']).collect()

print(f"\n【000001 复权因子】")
print(df.sort('trade_date').head(20))

print(f"\n【复权因子唯一值数量】: {df['adj_factor'].n_unique()}")
print(f"【复权因子变化日期】")
df_sorted = df.sort('trade_date')
prev_adj = None
for row in df_sorted.iter_rows():
    date, open_p, close_p, adj = row
    if prev_adj is not None and adj != prev_adj:
        print(f"  {date}: {prev_adj} -> {adj}")
    prev_adj = adj
