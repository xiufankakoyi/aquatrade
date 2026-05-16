"""
检查Tushare数据的真实含义
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("分析Tushare数据中的复权因子含义")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 读取000001的历史数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2024-01-01') &
    (pl.col('trade_date') <= '2025-02-28')
).select(['ts_code', 'trade_date', 'open', 'close', 'adj_factor']).collect()

print(f"\n【000001 复权因子变化】")
print(f"  最小复权因子: {df['adj_factor'].min()}")
print(f"  最大复权因子: {df['adj_factor'].max()}")
print(f"  复权因子唯一值数量: {df['adj_factor'].n_unique()}")

# 找出复权因子变化的日期
df_sorted = df.sort('trade_date')
adj_changes = df_sorted.filter(
    pl.col('adj_factor') != pl.col('adj_factor').shift(1)
)
print(f"\n【复权因子变化的日期】")
print(adj_changes[['trade_date', 'open', 'close', 'adj_factor']].head(20))

# 检查最新的复权因子
last_adj = df_sorted['adj_factor'].last()
print(f"\n【最新复权因子】: {last_adj}")

# Tushare的复权因子含义：
# 前复权价格 = 原始价格 × adj_factor / 最新adj_factor
# 如果adj_factor == 最新adj_factor，则前复权价格 = 原始价格

print("\n" + "=" * 70)
print("Tushare复权因子计算规则")
print("=" * 70)
print("""
Tushare的adj_factor含义：
- 前复权价格 = 原始价格 × adj_factor / 最新adj_factor

例如：
- 如果最新adj_factor = 127.7841
- 当前adj_factor = 127.7841
- 则前复权价格 = 原始价格 × 127.7841 / 127.7841 = 原始价格

这意味着：
- 数据库中存储的open/close就是【不复权价格】（原始价格）
- 当adj_factor == 最新adj_factor时，前复权价格 = 不复权价格

聚宽的动态复权：
- 交易价格：使用不复权价格（数据库中的open/close）
- 指标计算：使用动态前复权价格（需要用adj_factor调整）
""")

# 验证：计算前复权价格
print("\n【验证前复权价格计算】")
df_with_adj = df_sorted.with_columns([
    (pl.col('open') * pl.col('adj_factor') / last_adj).alias('open_adj'),
    (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj')
])
print(df_with_adj.filter(
    pl.col('trade_date').is_in(['2025-01-21', '2025-01-24'])
)[['trade_date', 'open', 'open_adj', 'close', 'close_adj', 'adj_factor']])
