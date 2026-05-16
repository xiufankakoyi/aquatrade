"""
检查预加载数据的列
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("检查预加载数据的列")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-01-31')
).collect()

print(f"\n【数据列】")
print(df.columns)

print(f"\n【数据样本】")
print(df.head(5))

print(f"\n【检查关键字段】")
required_fields = ['open', 'high', 'low', 'close', 'adj_factor']
for field in required_fields:
    if field in df.columns:
        print(f"  {field}: ✓ 存在")
    else:
        print(f"  {field}: ✗ 不存在")
