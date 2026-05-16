"""调试 join 过程"""
import polars as pl
import os

# 读取 stock_daily
parquet_path = 'data/parquet_data/stock_daily.parquet'
df_daily = pl.read_parquet(parquet_path)
df_daily = df_daily.filter(pl.col('trade_date') == '2025-01-02')

print(f'stock_daily 2025-01-02 行数: {len(df_daily)}')
print(f'stock_daily stock_code 示例: {df_daily["stock_code"].unique().to_list()[:20]}')
print()

# 读取 stock_info
info_path = 'data/parquet_data/stock_info.parquet'
info_df = pl.read_parquet(info_path)

print(f'stock_info 行数: {len(info_df)}')
print(f'stock_info stock_code 示例: {info_df["stock_code"].unique().to_list()[:20]}')
print()

# 检查 000030 在两张表中的情况
code = '000030'
print(f'检查 {code}:')
daily_match = df_daily.filter(pl.col('stock_code') == code)
info_match = info_df.filter(pl.col('stock_code') == code)
print(f'  stock_daily 中: {len(daily_match)} 条')
print(f'  stock_info 中: {len(info_match)} 条')
print()

# 执行 join
df_joined = df_daily.join(
    info_df.select(['stock_code', 'is_st', 'is_kc', 'is_cy']),
    on='stock_code',
    how='left'
)

print(f'join 后行数: {len(df_joined)}')
print(f'join 后 stock_code 示例: {df_joined["stock_code"].unique().to_list()[:20]}')
