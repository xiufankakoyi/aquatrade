"""检查备份数据详情"""
import polars as pl
from pathlib import Path

backup_file = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup_stock_daily.parquet')
df = pl.read_parquet(backup_file)

print('备份数据统计:')
print(f'总行数: {len(df):,}')
print(f'股票数: {df["ts_code"].n_unique()}')

# 检查日期分布
dates = df['trade_date'].dt.year()
year_counts = dates.value_counts().sort('trade_date')
print('\n按年份统计:')
for row in year_counts.iter_rows(named=True):
    print(f'  {row["trade_date"]}: {row["count"]:,} 行')

# 检查几只股票
print('\n检查样本股票:')
for ts_code in ['000001.SZ', '600000.SH', '600519.SH']:
    df_stock = df.filter(pl.col('ts_code') == ts_code)
    if len(df_stock) > 0:
        print(f'  {ts_code}: {len(df_stock)} 行, {df_stock["trade_date"].min()} ~ {df_stock["trade_date"].max()}')
