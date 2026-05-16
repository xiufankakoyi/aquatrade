"""
详细检查2025-03-07附近的MA数据
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
print("详细检查2025-03-07附近的MA数据")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date') >= '2025-03-03') &
    (pl.col('trade_date') <= '2025-03-12')
).select(['trade_date', 'open', 'close', 'ma5', 'ma10']).collect()

print(f"\n【数据库中的MA数据】")
print(df.sort('trade_date'))

# 使用收盘价重新计算MA
df_sorted = df.sort('trade_date')
prices = df_sorted['close'].to_numpy()
dates = df_sorted['trade_date'].to_list()

ma5_calc = pd.Series(prices).rolling(window=5).mean().values
ma10_calc = pd.Series(prices).rolling(window=10).mean().values

print(f"\n【重新计算MA】")
print(f"{'日期':<12} {'收盘价':<10} {'MA5(计算)':<12} {'MA10(计算)':<12} {'MA5(DB)':<10} {'MA10(DB)':<10}")
print("-" * 70)
for i, date in enumerate(dates):
    print(f"{date:<12} {prices[i]:<10.2f} {ma5_calc[i]:<12.2f} {ma10_calc[i]:<12.2f} {df_sorted['ma5'][i]:<10.2f} {df_sorted['ma10'][i]:<10.2f}")

# 检测金叉
print(f"\n【信号检测】")
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
        print(f"  金叉 @ {dates[i]}: MA5={curr_fast:.4f}, MA10={curr_slow:.4f}")
        print(f"    前一日: MA5={prev_fast:.4f}, MA10={prev_slow:.4f}")
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        print(f"  死叉 @ {dates[i]}: MA5={curr_fast:.4f}, MA10={curr_slow:.4f}")
        print(f"    前一日: MA5={prev_fast:.4f}, MA10={prev_slow:.4f}")
