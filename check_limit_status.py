import polars as pl
from pathlib import Path

parquet_file = Path('data/parquet_data/stock_limit_status.parquet')
print(f'文件大小: {parquet_file.stat().st_size / 1024 / 1024:.2f} MB')

# 读取并检查
df = pl.scan_parquet(str(parquet_file)).collect()
print(f'总行数: {len(df):,}')
min_date = df['trade_date'].min()
max_date = df['trade_date'].max()
print(f'日期范围: {min_date} 到 {max_date}')
print(f'唯一日期数: {df["trade_date"].n_unique()}')
print(f'唯一股票数: {df["stock_code"].n_unique()}')
