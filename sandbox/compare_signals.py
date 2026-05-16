"""
对比交易信号差异
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
print("对比交易信号差异")
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
close_prices = df_sorted['close'].to_numpy()
open_prices = df_sorted['open'].to_numpy()

# 使用数据库中的MA
ma5_db = df_sorted['ma5'].to_numpy()
ma10_db = df_sorted['ma10'].to_numpy()

# 重新计算MA
prices_series = pd.Series(close_prices)
ma5_calc = prices_series.rolling(window=5).mean().values
ma10_calc = prices_series.rolling(window=10).mean().values

print(f"\n【信号对比 - 使用数据库MA】")
signals_db = []
for i in range(1, len(dates) - 1):
    if np.isnan(ma5_db[i]) or np.isnan(ma10_db[i]):
        continue
    if np.isnan(ma5_db[i-1]) or np.isnan(ma10_db[i-1]):
        continue
    
    curr_fast = ma5_db[i]
    curr_slow = ma10_db[i]
    prev_fast = ma5_db[i-1]
    prev_slow = ma10_db[i-1]
    
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        signals_db.append((dates[i+1], 'buy', curr_fast, curr_slow))
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signals_db.append((dates[i+1], 'sell', curr_fast, curr_slow))

print(f"  总信号数: {len(signals_db)}")
for date, action, ma5, ma10 in signals_db[:10]:
    print(f"    {date}: {action}")

print(f"\n【信号对比 - 使用重新计算的MA】")
signals_calc = []
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
        signals_calc.append((dates[i+1], 'buy', curr_fast, curr_slow))
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signals_calc.append((dates[i+1], 'sell', curr_fast, curr_slow))

print(f"  总信号数: {len(signals_calc)}")
for date, action, ma5, ma10 in signals_calc[:10]:
    print(f"    {date}: {action}")

# 检查差异
print(f"\n【信号差异】")
db_dates = set(s[0] for s in signals_db)
calc_dates = set(s[0] for s in signals_calc)

only_db = db_dates - calc_dates
only_calc = calc_dates - db_dates

print(f"  仅数据库MA有: {sorted(only_db)}")
print(f"  仅计算MA有: {sorted(only_calc)}")

# 检查 2025-03-10 附近的MA
print(f"\n【2025-03-07 附近的MA对比】")
for i, date in enumerate(dates):
    if '2025-03-05' <= date <= '2025-03-12':
        print(f"  {date}: close={close_prices[i]:.2f}, MA5(DB)={ma5_db[i]:.2f}, MA10(DB)={ma10_db[i]:.2f}, MA5(calc)={ma5_calc[i]:.2f}, MA10(calc)={ma10_calc[i]:.2f}")
