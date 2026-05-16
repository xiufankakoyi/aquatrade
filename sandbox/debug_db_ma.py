"""
检查数据库中的MA字段
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np

print("=" * 70)
print("检查数据库中的MA字段")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date') >= '2025-02-20') &
    (pl.col('trade_date') <= '2025-04-10')
).select(['trade_date', 'close', 'ma5', 'ma10']).collect()

print(f"\n【数据库中的MA数据】")
print(df.sort('trade_date'))

# 检测金叉/死叉
df_sorted = df.sort('trade_date')
dates = df_sorted['trade_date'].to_list()
ma5_list = df_sorted['ma5'].to_numpy()
ma10_list = df_sorted['ma10'].to_numpy()

print(f"\n【使用数据库MA检测信号】")
for i in range(1, len(dates) - 1):
    if np.isnan(ma5_list[i]) or np.isnan(ma10_list[i]):
        continue
    if np.isnan(ma5_list[i-1]) or np.isnan(ma10_list[i-1]):
        continue
    
    curr_fast = ma5_list[i]
    curr_slow = ma10_list[i]
    prev_fast = ma5_list[i-1]
    prev_slow = ma10_list[i-1]
    
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        print(f"  金叉 @ {dates[i]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f} -> 信号在 {dates[i+1]}")
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        print(f"  死叉 @ {dates[i]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f} -> 信号在 {dates[i+1]}")
