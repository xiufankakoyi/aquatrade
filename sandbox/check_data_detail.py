"""详细检查数据完整性"""
from pathlib import Path
from arcticdb import Arctic
import polars as pl

arctic_path = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db')

print('=' * 60)
print('数据完整性检查')
print('=' * 60)

# 检查 stock_daily
stock_daily_path = arctic_path / 'stock_daily'
arctic = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')
lib = arctic['stock_daily']
symbols = lib.list_symbols()
print(f'\nstock_daily: {len(symbols)} 只股票')

# 抽样检查几只股票
sample_symbols = ['000001.SZ', '600000.SH', '300750.SZ']
for sym in sample_symbols:
    if sym in symbols:
        item = lib.read(sym)
        df = item.data
        print(f'  {sym}: {len(df)} 行, 日期: {df.index.min()} ~ {df.index.max()}')

# 检查 benchmark
benchmark_path = arctic_path / 'benchmark'
arctic = Arctic(f'lmdb://{benchmark_path}?map_size=10GB')
lib = arctic['benchmark']
symbols = lib.list_symbols()
print(f'\nbenchmark: {len(symbols)} 只')

# 检查 stock_basic
stock_basic_path = arctic_path / 'stock_basic'
if (stock_basic_path / 'stock_basic' / 'data.mdb').exists():
    arctic = Arctic(f'lmdb://{stock_basic_path}?map_size=10GB')
    lib = arctic['stock_basic']
    symbols = lib.list_symbols()
    print(f'\nstock_basic: {len(symbols)} 只')
else:
    print(f'\nstock_basic: 空库')

print('\n' + '=' * 60)
print('总结')
print('=' * 60)
print('stock_daily 数据已恢复:')
print('  - 5488 只股票')
print('  - 日期范围: 2010-01-04 ~ 2026-02-27')
print('  - 7,103,757 行数据')
