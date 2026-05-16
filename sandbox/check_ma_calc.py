"""
检查数据库MA的计算方式
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
print("检查数据库MA的计算方式")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取完整历史数据
df_full = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001')
).select(['trade_date', 'open', 'close', 'ma5', 'ma10']).collect()

df_full_sorted = df_full.sort('trade_date')
dates_full = df_full_sorted['trade_date'].to_list()
close_prices_full = df_full_sorted['close'].to_numpy()
ma5_db_full = df_full_sorted['ma5'].to_numpy()
ma10_db_full = df_full_sorted['ma10'].to_numpy()

print(f"\n【完整历史数据范围】")
print(f"  开始日期: {dates_full[0]}")
print(f"  结束日期: {dates_full[-1]}")
print(f"  总交易日: {len(dates_full)}")

# 检查2025年初的MA
print(f"\n【2025年初的MA对比】")
for i, date in enumerate(dates_full):
    if '2025-01-02' <= date <= '2025-01-15':
        # 使用完整历史数据计算MA
        prices_series_full = pd.Series(close_prices_full[:i+1])
        ma5_calc_full = prices_series_full.rolling(window=5).mean().iloc[-1] if len(prices_series_full) >= 5 else np.nan
        ma10_calc_full = prices_series_full.rolling(window=10).mean().iloc[-1] if len(prices_series_full) >= 10 else np.nan
        
        print(f"  {date}: close={close_prices_full[i]:.2f}, MA5(DB)={ma5_db_full[i]:.2f}, MA5(calc_full)={ma5_calc_full:.2f}, MA10(DB)={ma10_db_full[i]:.2f}, MA10(calc_full)={ma10_calc_full:.2f}")

# 检查2025-03-07附近的MA
print(f"\n【2025-03-07附近的MA对比】")
for i, date in enumerate(dates_full):
    if '2025-03-05' <= date <= '2025-03-12':
        prices_series_full = pd.Series(close_prices_full[:i+1])
        ma5_calc_full = prices_series_full.rolling(window=5).mean().iloc[-1] if len(prices_series_full) >= 5 else np.nan
        ma10_calc_full = prices_series_full.rolling(window=10).mean().iloc[-1] if len(prices_series_full) >= 10 else np.nan
        
        print(f"  {date}: close={close_prices_full[i]:.2f}, MA5(DB)={ma5_db_full[i]:.4f}, MA5(calc_full)={ma5_calc_full:.4f}, diff={ma5_db_full[i] - ma5_calc_full:.6f}")
