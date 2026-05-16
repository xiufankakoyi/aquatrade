"""
检查完整信号序列
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
print("检查完整信号序列")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-12-31')
).select(['trade_date', 'open', 'close', 'ma5', 'ma10']).collect()

df_sorted = df.sort('trade_date')
dates = df_sorted['trade_date'].to_list()
ma5_list = df_sorted['ma5'].to_numpy()
ma10_list = df_sorted['ma10'].to_numpy()

print(f"\n【所有信号】")
signals = []
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
        signals.append((dates[i+1], 'buy', curr_fast, curr_slow))
        print(f"  金叉 @ {dates[i]} -> 买入信号在 {dates[i+1]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f}")
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signals.append((dates[i+1], 'sell', curr_fast, curr_slow))
        print(f"  死叉 @ {dates[i]} -> 卖出信号在 {dates[i+1]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f}")

print(f"\n【模拟交易】")
position = 0
trades = []
for date, action, ma5, ma10 in signals:
    if action == 'buy' and position == 0:
        position = 1
        trades.append((date, 'buy'))
        print(f"  {date}: 买入")
    elif action == 'sell' and position == 1:
        position = 0
        trades.append((date, 'sell'))
        print(f"  {date}: 卖出")

print(f"\n【交易记录】")
for date, action in trades:
    print(f"  {date}: {action}")
