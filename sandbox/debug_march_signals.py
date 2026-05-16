"""
检查2025年3月的信号
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

from core.backtest.factor_matrix import FactorMatrixBuilder

print("=" * 70)
print("检查2025年3月的信号")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date') >= '2025-02-20') &
    (pl.col('trade_date') <= '2025-04-10')
).select(['trade_date', 'open', 'close', 'ma5', 'ma10', 'adj_factor']).collect()

print(f"\n【原始数据】")
print(df.sort('trade_date'))

# 计算MA
df_sorted = df.sort('trade_date')
prices = df_sorted['close'].to_numpy()
dates = df_sorted['trade_date'].to_list()

ma5_calc = pd.Series(prices).rolling(window=5).mean().values
ma10_calc = pd.Series(prices).rolling(window=10).mean().values

print(f"\n【计算MA并检测信号】")
for i in range(1, len(dates) - 1):
    if np.isnan(ma5_calc[i]) or np.isnan(ma10_calc[i]):
        continue
    if np.isnan(ma5_calc[i-1]) or np.isnan(ma10_calc[i-1]):
        continue
    
    curr_fast = ma5_calc[i]
    curr_slow = ma10_calc[i]
    prev_fast = ma5_calc[i-1]
    prev_slow = ma10_calc[i-1]
    
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        print(f"  金叉 @ {dates[i]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f} -> 信号在 {dates[i+1]}")
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        print(f"  死叉 @ {dates[i]}: MA5={curr_fast:.2f}, MA10={curr_slow:.2f} -> 信号在 {dates[i+1]}")
