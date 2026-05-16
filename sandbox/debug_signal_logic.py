"""
检查信号生成逻辑
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
print("检查信号生成逻辑")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-03-31')
).collect()

print(f"\n【原始数据】")
print(df.select(['trade_date', 'open', 'close', 'ma5', 'ma10', 'adj_factor']).sort('trade_date').head(30))

# 构建因子矩阵
print(f"\n【构建因子矩阵】")
builder = FactorMatrixBuilder()
fm = builder.build_from_single_dataframe(df, use_cache=False)

# 找到000001的索引
code_idx = fm.code_to_idx.get('000001', -1)
print(f"  000001索引: {code_idx}")

if code_idx >= 0:
    factor_idx = {name: i for i, name in enumerate(fm.factor_names)}
    close_idx = factor_idx.get('close', -1)
    close_adj_idx = factor_idx.get('close_adj', -1)
    ma5_idx = factor_idx.get('ma5', -1)
    ma10_idx = factor_idx.get('ma10', -1)
    
    print(f"\n【关键日期数据】")
    for t in range(len(fm.dates)):
        date = fm.dates[t]
        if date in ['2025-02-05', '2025-02-06', '2025-02-07', '2025-02-10', '2025-02-11']:
            close_val = fm.values[t, code_idx, close_idx] if close_idx >= 0 else np.nan
            close_adj_val = fm.values[t, code_idx, close_adj_idx] if close_adj_idx >= 0 else np.nan
            ma5_val = fm.values[t, code_idx, ma5_idx] if ma5_idx >= 0 else np.nan
            ma10_val = fm.values[t, code_idx, ma10_idx] if ma10_idx >= 0 else np.nan
            
            print(f"  {date}: close={close_val:.2f}, close_adj={close_adj_val:.2f}, ma5={ma5_val:.2f}, ma10={ma10_val:.2f}")
    
    print(f"\n【信号生成过程】")
    T = len(fm.dates)
    signals = np.zeros(T, dtype=np.int32)
    
    for t in range(1, T - 1):
        ma5_t = fm.values[t, code_idx, ma5_idx]
        ma10_t = fm.values[t, code_idx, ma10_idx]
        ma5_t1 = fm.values[t-1, code_idx, ma5_idx]
        ma10_t1 = fm.values[t-1, code_idx, ma10_idx]
        
        if np.isnan(ma5_t) or np.isnan(ma10_t) or np.isnan(ma5_t1) or np.isnan(ma10_t1):
            continue
        
        date = fm.dates[t]
        
        if ma5_t1 <= ma10_t1 and ma5_t > ma10_t:
            signals[t + 1] = 1
            print(f"  金叉 @ {date} (索引{t}): ma5_t1={ma5_t1:.2f} <= ma10_t1={ma10_t1:.2f}, ma5_t={ma5_t:.2f} > ma10_t={ma10_t:.2f}")
            print(f"    → 设置 signals[{t+1}] = 1 (日期: {fm.dates[t+1]})")
        
        if ma5_t1 >= ma10_t1 and ma5_t < ma10_t:
            signals[t + 1] = -1
            print(f"  死叉 @ {date} (索引{t}): ma5_t1={ma5_t1:.2f} >= ma10_t1={ma10_t1:.2f}, ma5_t={ma5_t:.2f} < ma10_t={ma10_t:.2f}")
            print(f"    → 设置 signals[{t+1}] = -1 (日期: {fm.dates[t+1]})")
