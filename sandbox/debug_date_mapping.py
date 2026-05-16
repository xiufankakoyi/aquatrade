"""
检查日期索引映射
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np

from core.backtest.factor_matrix import FactorMatrixBuilder

print("=" * 70)
print("检查日期索引映射")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('trade_date') >= '2024-12-01') &
    (pl.col('trade_date') <= '2025-03-31')
).collect()

# 构建因子矩阵
builder = FactorMatrixBuilder()
fm = builder.build_from_single_dataframe(df, use_cache=False)

print(f"\n【日期列表】")
for i, date in enumerate(fm.dates):
    if '2025-02-05' <= date <= '2025-02-15':
        print(f"  索引{i}: {date}")

# 模拟信号生成
print(f"\n【模拟信号生成】")
factor_idx = {name: i for i, name in enumerate(fm.factor_names)}
close_adj_idx = factor_idx.get('close_adj', -1)
code_idx = fm.code_to_idx.get('000001', -1)

close_adj = fm.values[:, code_idx, close_adj_idx]

import pandas as pd
prices_series = pd.Series(close_adj[~np.isnan(close_adj)])
ma_fast = prices_series.rolling(window=5).mean().values
ma_slow = prices_series.rolling(window=10).mean().values

# 重建完整MA数组
ma_fast_full = np.full(len(fm.dates), np.nan)
ma_slow_full = np.full(len(fm.dates), np.nan)
valid_mask = ~np.isnan(close_adj)
ma_fast_full[valid_mask] = ma_fast
ma_slow_full[valid_mask] = ma_slow

# 生成信号
signals = np.zeros(len(fm.dates), dtype=np.int8)
for t in range(1, len(fm.dates) - 1):
    if np.isnan(ma_fast_full[t]) or np.isnan(ma_slow_full[t]):
        continue
    if np.isnan(ma_fast_full[t-1]) or np.isnan(ma_slow_full[t-1]):
        continue
    
    curr_fast = ma_fast_full[t]
    curr_slow = ma_slow_full[t]
    prev_fast = ma_fast_full[t-1]
    prev_slow = ma_slow_full[t-1]
    
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        signals[t + 1] = 1
        print(f"  金叉 @ 索引{t} ({fm.dates[t]}): signals[{t+1}] = 1 ({fm.dates[t+1]})")
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signals[t + 1] = -1
        print(f"  死叉 @ 索引{t} ({fm.dates[t]}): signals[{t+1}] = -1 ({fm.dates[t+1]})")

print(f"\n【信号检查】")
for i, sig in enumerate(signals):
    if sig != 0 and '2025-02-05' <= fm.dates[i] <= '2025-02-15':
        print(f"  索引{i}: {fm.dates[i]} -> 信号={sig}")
