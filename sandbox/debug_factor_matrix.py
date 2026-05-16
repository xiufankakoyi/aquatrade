"""
详细检查因子矩阵构建过程
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
print("详细检查因子矩阵构建过程")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-01-31')
).collect()

print(f"\n【原始数据】")
print(f"  行数: {len(df)}")
print(f"  列数: {len(df.columns)}")
print(f"  列名: {df.columns}")

# 检查是否有 open_adj 等字段
print(f"\n【检查前复权价格字段】")
for field in ['open_adj', 'high_adj', 'low_adj', 'close_adj']:
    if field in df.columns:
        print(f"  {field}: ✓ 存在")
    else:
        print(f"  {field}: ✗ 不存在")

# 构建因子矩阵
print(f"\n【构建因子矩阵】")
builder = FactorMatrixBuilder()
fm = builder.build_from_single_dataframe(df, use_cache=False)

print(f"  T={len(fm.dates)}, N={len(fm.codes_str)}, F={len(fm.factor_names)}")
print(f"  因子名: {fm.factor_names}")

# 找到000001的索引
code_idx = fm.code_to_idx.get('000001', -1)
print(f"\n【000001索引】: {code_idx}")

if code_idx >= 0:
    # 检查价格数据
    factor_idx = {name: i for i, name in enumerate(fm.factor_names)}
    open_idx = factor_idx.get('open', -1)
    close_idx = factor_idx.get('close', -1)
    open_adj_idx = factor_idx.get('open_adj', -1)
    close_adj_idx = factor_idx.get('close_adj', -1)
    
    print(f"\n【因子索引】")
    print(f"  open: {open_idx}")
    print(f"  close: {close_idx}")
    print(f"  open_adj: {open_adj_idx}")
    print(f"  close_adj: {close_adj_idx}")
    
    print(f"\n【前5天价格数据】")
    for t in range(min(5, len(fm.dates))):
        date = fm.dates[t]
        open_val = fm.values[t, code_idx, open_idx] if open_idx >= 0 else np.nan
        close_val = fm.values[t, code_idx, close_idx] if close_idx >= 0 else np.nan
        open_adj_val = fm.values[t, code_idx, open_adj_idx] if open_adj_idx >= 0 else np.nan
        close_adj_val = fm.values[t, code_idx, close_adj_idx] if close_adj_idx >= 0 else np.nan
        
        print(f"  {date}: open={open_val:.2f}, close={close_val:.2f}, open_adj={open_adj_val:.2f}, close_adj={close_adj_val:.2f}")
