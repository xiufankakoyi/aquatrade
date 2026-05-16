"""从备份恢复 stock_daily 数据"""
from pathlib import Path
import polars as pl
from arcticdb import Arctic
from loguru import logger
from datetime import datetime
import sys

logger.remove()
logger.add(sys.stderr, level="INFO")

backup_file = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup_stock_daily.parquet')
arctic_path = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db/stock_daily')

print('=' * 60)
print('恢复 stock_daily 数据')
print('=' * 60)

print(f'\n1. 读取备份文件...')
df = pl.read_parquet(backup_file)
print(f'   行数: {len(df):,}')
print(f'   股票数: {df["ts_code"].n_unique():,}')
print(f'   日期范围: {df["trade_date"].min()} ~ {df["trade_date"].max()}')

print(f'\n2. 连接 ArcticDB...')
arctic = Arctic(f'lmdb://{arctic_path}?map_size=10GB')
lib = arctic['stock_daily']
existing_symbols = lib.list_symbols()
print(f'   现有 symbols: {len(existing_symbols)}')

print(f'\n3. 按股票分组写入...')
start_time = datetime.now()

# 按股票代码分组
ts_codes = df['ts_code'].unique().to_list()
total = len(ts_codes)
success = 0
failed = 0

for i, ts_code in enumerate(ts_codes):
    try:
        stock_df = df.filter(pl.col('ts_code') == ts_code)
        stock_df = stock_df.sort('trade_date')
        stock_df_pd = stock_df.to_pandas()
        stock_df_pd.set_index('trade_date', inplace=True)
        
        lib.write(ts_code, stock_df_pd, metadata={
            'symbol': ts_code,
            'rows': len(stock_df),
            'start_date': str(stock_df['trade_date'].min()),
            'end_date': str(stock_df['trade_date'].max()),
            'restored_at': datetime.now().isoformat()
        })
        success += 1
        
        if (i + 1) % 500 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f'   进度: {i+1}/{total} ({(i+1)/total*100:.1f}%) - ETA: {eta:.0f}s')
    except Exception as e:
        failed += 1
        if failed <= 5:
            print(f'   失败: {ts_code} - {e}')

elapsed = (datetime.now() - start_time).total_seconds()
print(f'\n4. 恢复完成!')
print(f'   成功: {success}')
print(f'   失败: {failed}')
print(f'   耗时: {elapsed:.1f}s')

# 验证
symbols = lib.list_symbols()
print(f'\n5. 验证:')
print(f'   库中 symbols: {len(symbols)}')
