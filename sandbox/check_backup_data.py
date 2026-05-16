import polars as pl
from pathlib import Path

backup_dir = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
f = backup_dir / 'stock_daily.parquet'

df = pl.read_parquet(f)
print(f'备份文件行数: {len(df):,}')
min_date = df['trade_date'].min()
max_date = df['trade_date'].max()
print(f'日期范围: {min_date} ~ {max_date}')
print(f'股票数: {df["ts_code"].n_unique():,}')
