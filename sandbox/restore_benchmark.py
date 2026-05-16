"""
恢复基准数据
"""
from pathlib import Path
import polars as pl
from arcticdb import Arctic
import shutil

BACKUP_DIR = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
ARCTIC_PATH = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db')

# 删除现有库
lib_path = ARCTIC_PATH / 'benchmark_daily'
if lib_path.exists():
    shutil.rmtree(lib_path)
    print(f'已删除: {lib_path}')

# 创建新库
lib_path.mkdir(parents=True, exist_ok=True)
arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
arctic.create_library('benchmark_daily')
lib = arctic['benchmark_daily']

# 读取备份
backup_file = BACKUP_DIR / 'benchmark_daily.parquet'
df = pl.read_parquet(backup_file)
print(f'备份: {len(df):,} 行')
print(f'日期范围: {df["date"].min()} ~ {df["date"].max()}')

# 按代码分组写入
codes = df['code'].unique().to_list()
print(f'指数数: {len(codes)}')

for code in codes:
    code_df = df.filter(pl.col('code') == code)
    code_df = code_df.sort('date')
    
    # 转换日期格式
    code_df = code_df.with_columns([
        pl.col('date').str.replace('-', '').alias('trade_date')
    ])
    
    # 添加 ts_code
    code_df = code_df.with_columns([
        (pl.col('code') + '.SH').alias('ts_code')
    ])
    
    symbol = code + '.SH'
    lib._nvs.write(symbol, code_df.to_arrow())
    print(f'  写入: {symbol} ({len(code_df)} 行)')

print('完成!')
