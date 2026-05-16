"""
详细调试信号生成过程
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np
import pandas as pd

print("=" * 70)
print("详细调试信号生成")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2024-12-01') &
    (pl.col('trade_date') <= '2025-02-28')
).select(['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'adj_factor']).collect().sort('trade_date')

last_adj = df['adj_factor'].last()
df_adj = df.with_columns([
    (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj')
])

close_adj = df_adj['close_adj'].to_numpy()
dates = df_adj['trade_date'].to_numpy()

ma5 = pd.Series(close_adj).rolling(window=5).mean().values
ma10 = pd.Series(close_adj).rolling(window=10).mean().values

print("\n【日期索引和MA数据】")
print(f"{'索引':<5} {'日期':<12} {'收盘':<8} {'MA5':<10} {'MA10':<10} {'信号'}")
print("-" * 60)

signals = np.zeros(len(dates), dtype=np.int8)

for t in range(1, len(dates) - 1):
    if np.isnan(ma5[t]) or np.isnan(ma10[t]) or np.isnan(ma5[t-1]) or np.isnan(ma10[t-1]):
        continue
    
    curr_fast = ma5[t]
    curr_slow = ma10[t]
    prev_fast = ma5[t-1]
    prev_slow = ma10[t-1]
    
    signal = ""
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        signals[t + 1] = 1
        signal = f"金叉→T+1买入(索引{t+1})"
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signals[t + 1] = -1
        signal = f"死叉→T+1卖出(索引{t+1})"
    
    if signal or dates[t] in ['2025-01-20', '2025-01-21', '2025-01-23', '2025-01-24', '2025-02-06', '2025-02-07', '2025-02-10']:
        print(f"{t:<5} {dates[t]:<12} {close_adj[t]:<8.2f} {curr_fast:<10.2f} {curr_slow:<10.2f} {signal}")

print("\n【信号矩阵】")
for t in range(len(dates)):
    if signals[t] != 0:
        print(f"  索引{t}: {dates[t]} 信号={signals[t]} ({'买入' if signals[t]==1 else '卖出'})")

print("\n【聚宽交易记录】")
print("  2025-01-21: buy")
print("  2025-01-24: sell")
print("  2025-02-10: buy")
print("  2025-02-27: sell")

print("\n【对比】")
print("AquaTrade应该在以下日期交易：")
for t in range(len(dates)):
    if signals[t] != 0:
        print(f"  {dates[t]}: {'买入' if signals[t]==1 else '卖出'}")
