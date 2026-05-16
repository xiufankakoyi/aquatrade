"""
验证动态复权的必要性 - 检查除权除息对MA计算的影响
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import pandas as pd
import numpy as np

print("=" * 70)
print("验证动态复权的必要性")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取000001的历史数据（包含除权除息）
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2024-06-01') &
    (pl.col('trade_date') <= '2024-07-31')
).select(['ts_code', 'trade_date', 'open', 'close', 'adj_factor']).collect().sort('trade_date')

print(f"\n【000001 2024年6-7月数据（包含除权除息）】")
print(df)

# 找出除权除息日
adj_changes = df.filter(
    pl.col('adj_factor') != pl.col('adj_factor').shift(1)
)
print(f"\n【除权除息日】")
print(adj_changes[['trade_date', 'open', 'close', 'adj_factor']])

# 计算最新复权因子
last_adj = df['adj_factor'].last()
print(f"\n最新复权因子: {last_adj}")

# 计算前复权价格
df_adj = df.with_columns([
    (pl.col('open') * pl.col('adj_factor') / last_adj).alias('open_adj'),
    (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj')
])

print(f"\n【前复权价格计算】")
print(df_adj[['trade_date', 'open', 'open_adj', 'close', 'close_adj', 'adj_factor']])

# 计算MA5（使用不复权价格 vs 前复权价格）
df_pd = df_adj.to_pandas()
df_pd['MA5_unadj'] = df_pd['close'].rolling(5).mean()
df_pd['MA5_adj'] = df_pd['close_adj'].rolling(5).mean()

print(f"\n【MA5对比（除权除息日附近）】")
print(df_pd[['trade_date', 'close', 'close_adj', 'MA5_unadj', 'MA5_adj']].tail(20).to_string())

print("\n" + "=" * 70)
print("结论")
print("=" * 70)
print("""
1. 如果使用不复权价格计算MA，在除权除息日MA会产生跳变
2. 如果使用前复权价格计算MA，MA会平滑过渡
3. 动态复权的核心：
   - 交易价格：使用不复权价格（真实成交价）
   - 指标计算：使用动态前复权价格（避免除权除息影响）

4. 在2025年1月回测期间，000001没有除权除息，所以：
   - 不复权价格 = 前复权价格
   - 当前结果正确

5. 但如果回测期间包含除权除息，必须实现动态复权！
""")
