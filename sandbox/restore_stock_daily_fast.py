"""
快速恢复 stock_daily 数据（使用批量写入）

备份: 15,343,669 行, 2000-2025
"""
from pathlib import Path
import polars as pl
from arcticdb import Arctic
from datetime import datetime
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

BACKUP_DIR = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
ARCTIC_PATH = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db')


def get_arctic_lib(lib_name: str):
    lib_path = ARCTIC_PATH / lib_name
    lib_path.mkdir(parents=True, exist_ok=True)
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    
    existing = arctic.list_libraries()
    if lib_name not in existing:
        arctic.create_library(lib_name)
    
    return arctic[lib_name]


def restore_stock_daily():
    print('=' * 70)
    print('恢复 stock_daily（批量写入）')
    print('=' * 70)
    
    backup_file = BACKUP_DIR / 'stock_daily.parquet'
    print(f'读取备份: {backup_file}')
    
    df = pl.read_parquet(backup_file)
    print(f'  总行数: {len(df):,}')
    print(f'  股票数: {df["ts_code"].n_unique():,}')
    
    lib = get_arctic_lib('stock_daily')
    
    ts_codes = df['ts_code'].unique().to_list()
    total = len(ts_codes)
    print(f'\n写入 {total} 只股票...')
    
    start_time = datetime.now()
    
    # 批量写入（每批 500 只股票）
    batch_size = 500
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_codes = ts_codes[batch_start:batch_end]
        
        symbols = []
        data_list = []
        
        for ts_code in batch_codes:
            stock_df = df.filter(pl.col('ts_code') == ts_code)
            stock_df = stock_df.sort('trade_date')
            symbols.append(ts_code)
            data_list.append(stock_df.to_arrow())
        
        # 批量写入
        lib._nvs.batch_write(symbols, data_vector=data_list)
        
        # 进度
        elapsed = (datetime.now() - start_time).total_seconds()
        progress = batch_end / total * 100
        eta = (total - batch_end) / (batch_end / elapsed) if elapsed > 0 else 0
        print(f'  进度: {batch_end}/{total} ({progress:.1f}%) - ETA: {eta:.0f}s')
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f'\n完成: {total} 只股票, 耗时: {elapsed:.1f}s')


if __name__ == '__main__':
    restore_stock_daily()
