"""
继续恢复因子数据
"""
from pathlib import Path
import polars as pl
from arcticdb import Arctic
from datetime import datetime

BACKUP_DIR = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')
ARCTIC_PATH = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db')


def get_arctic_lib(lib_name: str) -> tuple:
    lib_path = ARCTIC_PATH / lib_name
    lib_path.mkdir(parents=True, exist_ok=True)
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    
    existing = arctic.list_libraries()
    if lib_name not in existing:
        arctic.create_library(lib_name)
    
    return arctic, arctic[lib_name]


def write_arrow(lib, symbol: str, arrow_table, metadata: dict = None):
    lib._nvs.write(symbol, arrow_table, metadata=metadata)


def restore_factors():
    print('=' * 70)
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
    restore_factors()
    restore_stock_info()
    verify_data()
    print('\n完成!')
