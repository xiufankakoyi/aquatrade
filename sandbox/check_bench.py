import polars as pl
from pathlib import Path

backup_dir = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
f = backup_dir / 'benchmark_daily.parquet'

df = pl.read_parquet(f)
print('备份基准数据:')
print(f'  行数: {len(df):,}')
print(f'  列: {df.columns}')
min_date = df['date'].min()
max_date = df['date'].max()
print(f'  日期范围: {min_date} ~ {max_date}')
print(df.head(3))
