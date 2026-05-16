"""
完整数据恢复脚本 - 使用 Polars + Arrow 零拷贝

恢复内容：
1. stock_daily: 2000-2025 日线数据（15,343,669 行）
2. benchmark_daily: 基准指数数据
3. factors: 因子数据（2020-2025）

工作流：Polars → to_arrow() → _nvs.write() → lib.read() → pl.from_arrow()
"""
from pathlib import Path
import polars as pl
import numpy as np
from arcticdb import Arctic
from loguru import logger
from datetime import datetime
import sys

logger.remove()
logger.add(sys.stderr, level="WARNING")

BACKUP_DIR = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
ARCTIC_PATH = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db')


def get_arctic_lib(lib_name: str) -> tuple:
    """获取 ArcticDB 库（独立实例模式）"""
    lib_path = ARCTIC_PATH / lib_name
    lib_path.mkdir(parents=True, exist_ok=True)
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    
    existing = arctic.list_libraries()
    if lib_name not in existing:
        arctic.create_library(lib_name)
    
    return arctic, arctic[lib_name]


def write_arrow(lib, symbol: str, arrow_table, metadata: dict = None):
    """直接写入 Arrow Table（零拷贝）"""
    lib._nvs.write(symbol, arrow_table, metadata=metadata)


def restore_stock_daily():
    """恢复日线数据"""
    print('\n' + '=' * 70)
    print('恢复 stock_daily')
    print('=' * 70)
    
    backup_file = BACKUP_DIR / 'stock_daily.parquet'
    if not backup_file.exists():
        print(f'备份文件不存在: {backup_file}')
        return
    
    print(f'读取备份: {backup_file}')
    df = pl.read_parquet(backup_file)
    print(f'  总行数: {len(df):,}')
    print(f'  股票数: {df["ts_code"].n_unique():,}')
    print(f'  日期范围: {df["trade_date"].min()} ~ {df["trade_date"].max()}')
    
    arctic, lib = get_arctic_lib('stock_daily')
    
    ts_codes = df['ts_code'].unique().to_list()
    total = len(ts_codes)
    print(f'\n写入 {total} 只股票（Arrow 零拷贝）...')
    
    start_time = datetime.now()
    success = 0
    
    for i, ts_code in enumerate(ts_codes):
        try:
            stock_df = df.filter(pl.col('ts_code') == ts_code)
            stock_df = stock_df.sort('trade_date')
            
            write_arrow(lib, ts_code, stock_df.to_arrow(), metadata={
                'symbol': ts_code,
                'rows': len(stock_df),
                'start_date': str(stock_df['trade_date'].min()),
                'end_date': str(stock_df['trade_date'].max()),
            })
            success += 1
            
            if (i + 1) % 1000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                eta = (total - i - 1) / ((i + 1) / elapsed) if elapsed > 0 else 0
                print(f'  进度: {i+1}/{total} ({(i+1)/total*100:.1f}%) - ETA: {eta:.0f}s')
        except Exception as e:
            if success < 3:
                print(f'  失败: {ts_code} - {e}')
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f'\n完成: {success}/{total}, 耗时: {elapsed:.1f}s')


def restore_benchmark_daily():
    """恢复基准指数数据"""
    print('\n' + '=' * 70)
    print('恢复 benchmark_daily')
    print('=' * 70)
    
    backup_file = BACKUP_DIR / 'benchmark_daily.parquet'
    if not backup_file.exists():
        print(f'备份文件不存在: {backup_file}')
        return
    
    print(f'读取备份: {backup_file}')
    df = pl.read_parquet(backup_file)
    print(f'  总行数: {len(df):,}')
    print(f'  列: {df.columns}')
    
    arctic, lib = get_arctic_lib('benchmark_daily')
    
    if 'index_code' in df.columns:
        codes = df['index_code'].unique().to_list()
    elif 'ts_code' in df.columns:
        codes = df['ts_code'].unique().to_list()
    else:
        codes = ['benchmark']
    
    print(f'\n写入 {len(codes)} 个指数...')
    
    for code in codes:
        try:
            if 'index_code' in df.columns:
                code_df = df.filter(pl.col('index_code') == code)
            elif 'ts_code' in df.columns:
                code_df = df.filter(pl.col('ts_code') == code)
            else:
                code_df = df
            
            if len(code_df) > 0:
                write_arrow(lib, code, code_df.to_arrow(), metadata={
                    'symbol': code,
                    'rows': len(code_df),
                })
                print(f'  写入: {code} ({len(code_df)} 行)')
        except Exception as e:
            print(f'  失败: {code} - {e}')
    
    print('完成')


def restore_factors():
    """恢复因子数据（2020-2025）"""
    print('\n' + '=' * 70)
    print('恢复 factor')
    print('=' * 70)
    
    arctic, lib = get_arctic_lib('factor')
    
    factor_files = [
        ('factors_valuation_hot.parquet', 'valuation'),
        ('factors_momentum_hot.parquet', 'momentum'),
    ]
    
    for filename, factor_type in factor_files:
        backup_file = BACKUP_DIR / filename
        if not backup_file.exists():
            print(f'跳过: {filename}')
            continue
        
        print(f'\n读取: {filename}')
        df = pl.read_parquet(backup_file)
        print(f'  行数: {len(df):,}')
        print(f'  列: {df.columns}')
        
        # 支持 stock_code 或 ts_code
        code_col = 'stock_code' if 'stock_code' in df.columns else 'ts_code'
        codes = df[code_col].unique().to_list()
        print(f'  写入 {len(codes)} 只股票...')
        
        start_time = datetime.now()
        for i, code in enumerate(codes):
            try:
                stock_df = df.filter(pl.col(code_col) == code)
                stock_df = stock_df.sort('trade_date')
                
                symbol = f"{factor_type}_{code}"
                write_arrow(lib, symbol, stock_df.to_arrow(), metadata={
                    'type': factor_type,
                    'symbol': code,
                    'rows': len(stock_df),
                })
            except Exception as e:
                pass
            
            if (i + 1) % 2000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f'  进度: {i+1}/{len(codes)} ({(i+1)/len(codes)*100:.1f}%)')
        
        print(f'  完成: {filename}')


def restore_stock_info():
    """恢复股票基本信息"""
    print('\n' + '=' * 70)
    print('恢复 stock_info')
    print('=' * 70)
    
    backup_file = BACKUP_DIR / 'stock_info.parquet'
    if not backup_file.exists():
        print(f'备份文件不存在: {backup_file}')
        return
    
    print(f'读取备份: {backup_file}')
    df = pl.read_parquet(backup_file)
    print(f'  总行数: {len(df):,}')
    
    arctic, lib = get_arctic_lib('stock_info')
    
    write_arrow(lib, 'stock_info', df.to_arrow(), metadata={
        'rows': len(df),
    })
    
    print('完成')


def verify_data():
    """验证数据"""
    print('\n' + '=' * 70)
    print('验证数据')
    print('=' * 70)
    
    libs = ['stock_daily', 'benchmark_daily', 'factor', 'stock_info']
    
    for lib_name in libs:
        try:
            arctic, lib = get_arctic_lib(lib_name)
            symbols = lib.list_symbols()
            print(f'{lib_name}: {len(symbols)} symbols')
        except Exception as e:
            print(f'{lib_name}: 错误 - {e}')


if __name__ == '__main__':
    print('=' * 70)
    print('AquaTrade 数据恢复（Arrow 零拷贝）')
    print('=' * 70)
    print(f'开始时间: {datetime.now()}')
    
    restore_stock_daily()
    restore_benchmark_daily()
    restore_factors()
    restore_stock_info()
    verify_data()
    
    print('\n' + '=' * 70)
    print('恢复完成')
    print('=' * 70)
