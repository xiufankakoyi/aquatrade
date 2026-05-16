"""
检查股票代码格式
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("检查股票代码格式")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-01-10')
).select(['stock_code', 'trade_date', 'open', 'close']).collect()

print(f"\n【股票代码格式】")
print(df['stock_code'].unique().head(10))

print(f"\n【日期格式】")
print(df['trade_date'].unique().head(10))

print(f"\n【数据样本】")
print(df.filter(pl.col('stock_code') == '000001').head(5))
