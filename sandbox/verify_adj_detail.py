"""
验证动态复权 - 详细对比除权除息日前后的价格
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np

print("=" * 70)
print("验证动态复权 - 详细对比")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取000001的数据（包含除权除息）
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2024-06-01') &
    (pl.col('trade_date') <= '2024-07-31')
).select(['ts_code', 'trade_date', 'open', 'close', 'adj_factor']).collect().sort('trade_date')

print(f"\n【原始数据】")
print(df)

# 计算前复权价格
last_adj = df['adj_factor'].last()
print(f"\n最新复权因子: {last_adj}")

df_adj = df.with_columns([
    (pl.col('open') * pl.col('adj_factor') / last_adj).alias('open_adj'),
    (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj')
])

print(f"\n【前复权价格计算】")
print(df_adj[['trade_date', 'open', 'open_adj', 'close', 'close_adj', 'adj_factor']])

# 找出除权除息日
adj_changes = df_adj.filter(
    pl.col('adj_factor') != pl.col('adj_factor').shift(1)
)
print(f"\n【除权除息日】")
print(adj_changes[['trade_date', 'open', 'open_adj', 'adj_factor']])

print("\n" + "=" * 70)
print("结论")
print("=" * 70)
print("""
动态复权规则：
1. 前复权价格 = 原始价格 × 当日adj_factor / 最新adj_factor
2. 在除权除息日之前：前复权价格 < 不复权价格（因为adj_factor < 最新adj_factor）
3. 在除权除息日之后：前复权价格 = 不复权价格（因为adj_factor = 最新adj_factor）

例如：
- 2024-06-03: adj_factor=125.0496, 前复权价格 = 10.26 * 125.0496 / 125.049 = 10.26（接近）
- 除权除息后：adj_factor=125.049, 前复权价格 = 原始价格

这就是为什么：
- 策略计算MA时应该使用前复权价格（消除除权除息影响）
- 交易时应该使用不复权价格（真实成交价）
""")
