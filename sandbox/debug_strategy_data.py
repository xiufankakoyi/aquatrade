"""
检查策略接收到的数据
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
print("检查策略接收到的数据")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('trade_date') >= '2024-12-01') &
    (pl.col('trade_date') <= '2025-03-31')
).collect()

print(f"\n【原始数据】")
print(f"  行数: {len(df)}")

# 构建因子矩阵
print(f"\n【构建因子矩阵】")
builder = FactorMatrixBuilder()
fm = builder.build_from_single_dataframe(df, use_cache=False)

print(f"  T={len(fm.dates)}, N={len(fm.codes_str)}, F={len(fm.factor_names)}")

# 找到000001的索引
code_idx = fm.code_to_idx.get('000001', -1)
print(f"  000001索引: {code_idx}")

if code_idx >= 0:
    factor_idx = {name: i for i, name in enumerate(fm.factor_names)}
    close_idx = factor_idx.get('close', -1)
    close_adj_idx = factor_idx.get('close_adj', -1)
    ma5_idx = factor_idx.get('ma5', -1)
    ma10_idx = factor_idx.get('ma10', -1)
    adj_factor_idx = factor_idx.get('adj_factor', -1)
    
    print(f"\n【检查 adj_factor】")
    adj_factors = fm.values[:, code_idx, adj_factor_idx]
    print(f"  adj_factor 前10个: {adj_factors[:10]}")
    print(f"  adj_factor 后10个: {adj_factors[-10:]}")
    
    print(f"\n【检查 close vs close_adj】")
    for t in range(min(10, len(fm.dates))):
        date = fm.dates[t]
        close_val = fm.values[t, code_idx, close_idx]
        close_adj_val = fm.values[t, code_idx, close_adj_idx]
        print(f"  {date}: close={close_val:.2f}, close_adj={close_adj_val:.2f}")
    
    print(f"\n【检查 ma5 vs 原始 ma5】")
    for t in range(min(10, len(fm.dates))):
        date = fm.dates[t]
        ma5_val = fm.values[t, code_idx, ma5_idx]
        print(f"  {date}: ma5={ma5_val:.2f}")
