"""检查备份数据"""
from pathlib import Path
import polars as pl

backup_file = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup_stock_daily.parquet')
if backup_file.exists():
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f'备份文件大小: {size_mb:.2f} MB')
    
    df = pl.read_parquet(backup_file)
    print(f'行数: {len(df):,}')
    print(f'列数: {len(df.columns)}')
    
    if 'ts_code' in df.columns:
        print(f'股票数: {df["ts_code"].n_unique()}')
    
    if 'trade_date' in df.columns:
        dates = df['trade_date']
        print(f'日期范围: {dates.min()} ~ {dates.max()}')
    
    print('\n列名:')
    print(df.columns)
else:
    print('备份文件不存在')
