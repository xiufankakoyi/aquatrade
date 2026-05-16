"""
检查股票代码映射
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np

from core.backtest.factor_matrix import FactorMatrixBuilder, stock_codes_to_int_vectorized_polars

print("=" * 70)
print("检查股票代码映射")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-01-31')
).collect()

# 获取股票代码列表
stock_codes = df['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()
stock_codes = [str(c).zfill(6) for c in stock_codes]

print(f"\n【股票代码列表前10个】")
print(stock_codes[:10])

# 检查 '000001' 是否在列表中
if '000001' in stock_codes:
    print(f"\n✓ '000001' 在股票代码列表中，索引: {stock_codes.index('000001')}")
else:
    print(f"\n✗ '000001' 不在股票代码列表中")

# 转换为 int32
codes_int = stock_codes_to_int_vectorized_polars(pl.Series(stock_codes))
print(f"\n【codes_int 前10个】")
print(codes_int[:10])

# 构建 code_to_idx
code_to_idx = {str(c): i for i, c in enumerate(codes_int)}
print(f"\n【code_to_idx 前10个】")
for i, (k, v) in enumerate(code_to_idx.items()):
    if i >= 10:
        break
    print(f"  '{k}': {v}")

# 检查 '1000001' 是否在 code_to_idx 中
if '1000001' in code_to_idx:
    print(f"\n✓ '1000001' 在 code_to_idx 中，索引: {code_to_idx['1000001']}")
else:
    print(f"\n✗ '1000001' 不在 code_to_idx 中")
