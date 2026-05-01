"""
回测 API 性能测试

目标：一年回测 < 2秒
"""
import sys
from pathlib import Path
import time
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arcticdb import Arctic
import polars as pl

ARCTIC_PATH = project_root / 'data' / 'arctic_db'


def get_arctic_lib(lib_name: str):
    lib_path = ARCTIC_PATH / lib_name
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    return arctic[lib_name]


def test_stock_data_query():
    """测试股票数据查询性能"""
    print('\n' + '=' * 70)
    print('测试股票数据查询性能')
    print('=' * 70)
    
    lib = get_arctic_lib('stock_daily')
    
    # 获取一个股票的数据
    symbols = lib.list_symbols()
    print(f'可用股票数: {len(symbols)}')
    
    if not symbols:
        print('没有股票数据')
        return
    
    test_symbol = symbols[0]
    print(f'测试股票: {test_symbol}')
    
    # 测试读取性能
    start = time.time()
    item = lib.read(test_symbol)
    df = pl.from_arrow(item.data)
    elapsed = time.time() - start
    
    print(f'读取耗时: {elapsed*1000:.1f}ms')
    print(f'数据行数: {len(df):,}')
    print(f'日期范围: {df["trade_date"].min()} ~ {df["trade_date"].max()}')


def test_benchmark_query():
    """测试基准数据查询性能"""
    print('\n' + '=' * 70)
    print('测试基准数据查询性能')
    print('=' * 70)
    
    lib = get_arctic_lib('benchmark_daily')
    
    symbols = lib.list_symbols()
    print(f'可用指数: {symbols}')
    
    if not symbols:
        print('没有指数数据')
        return
    
    # 测试读取
    start = time.time()
    item = lib.read('000001.SH')
    df = pl.from_arrow(item.data)
    elapsed = time.time() - start
    
    print(f'读取耗时: {elapsed*1000:.1f}ms')
    print(f'数据行数: {len(df):,}')


def test_year_backtest():
    """测试一年回测性能"""
    print('\n' + '=' * 70)
    print('测试一年回测性能（目标 < 2s）')
    print('=' * 70)
    
    lib_stock = get_arctic_lib('stock_daily')
    lib_bench = get_arctic_lib('benchmark_daily')
    
    # 获取股票列表
    symbols = lib_stock.list_symbols()
    print(f'股票数: {len(symbols)}')
    
    # 测试参数
    start_date = '2024-01-01'
    end_date = '2024-12-31'
    start_date_bench = '20240101'
    end_date_bench = '20241231'
    
    total_start = time.time()
    
    # 1. 获取基准数据
    t1 = time.time()
    bench_item = lib_bench.read('000001.SH')
    bench_df = pl.from_arrow(bench_item.data)
    bench_df = bench_df.filter(
        (pl.col('trade_date') >= start_date_bench) & 
        (pl.col('trade_date') <= end_date_bench)
    )
    t1_elapsed = time.time() - t1
    print(f'基准数据: {t1_elapsed*1000:.1f}ms ({len(bench_df)} 行)')
    
    # 2. 获取多只股票数据（模拟回测）
    t2 = time.time()
    test_symbols = symbols[:100]  # 测试100只股票
    
    stock_data = {}
    for sym in test_symbols:
        try:
            item = lib_stock.read(sym)
            df = pl.from_arrow(item.data)
            df = df.filter(
                (pl.col('trade_date') >= start_date) & 
                (pl.col('trade_date') <= end_date)
            )
            if len(df) > 0:
                stock_data[sym] = df
        except:
            pass
    
    t2_elapsed = time.time() - t2
    print(f'股票数据: {t2_elapsed*1000:.1f}ms ({len(stock_data)} 只)')
    
    # 3. 简单回测计算
    t3 = time.time()
    results = []
    for sym, df in stock_data.items():
        if 'close' in df.columns and len(df) > 1:
            close = df['close'].to_numpy()
            ret = (close[-1] - close[0]) / close[0]
            results.append({'symbol': sym, 'return': ret})
    
    t3_elapsed = time.time() - t3
    print(f'回测计算: {t3_elapsed*1000:.1f}ms')
    
    total_elapsed = time.time() - total_start
    print(f'\n总耗时: {total_elapsed:.2f}s')
    
    if total_elapsed < 2:
        print('✅ 性能达标（< 2s）')
    else:
        print('❌ 性能未达标')


def test_single_stock_query():
    """测试单股票查询性能（目标 < 500ms）"""
    print('\n' + '=' * 70)
    print('测试单股票查询性能（目标 < 500ms）')
    print('=' * 70)
    
    lib_stock = get_arctic_lib('stock_daily')
    lib_factor = get_arctic_lib('factor')
    
    symbols = lib_stock.list_symbols()
    test_symbol = symbols[0] if symbols else '000001.SZ'
    
    print(f'测试股票: {test_symbol}')
    
    total_start = time.time()
    
    # 1. 获取股票日线
    t1 = time.time()
    item = lib_stock.read(test_symbol)
    df = pl.from_arrow(item.data)
    t1_elapsed = time.time() - t1
    print(f'日线数据: {t1_elapsed*1000:.1f}ms ({len(df)} 行)')
    
    # 2. 获取因子数据
    t2 = time.time()
    factor_symbols = lib_factor.list_symbols()
    factor_data = {}
    for fs in factor_symbols:
        if test_symbol.replace('.SZ', '').replace('.SH', '') in fs:
            try:
                item = lib_factor.read(fs)
                factor_data[fs] = pl.from_arrow(item.data)
            except:
                pass
    t2_elapsed = time.time() - t2
    print(f'因子数据: {t2_elapsed*1000:.1f}ms ({len(factor_data)} 个因子)')
    
    total_elapsed = time.time() - total_start
    print(f'\n总耗时: {total_elapsed*1000:.1f}ms')
    
    if total_elapsed < 0.5:
        print('✅ 性能达标（< 500ms）')
    else:
        print('❌ 性能未达标')


if __name__ == '__main__':
    test_stock_data_query()
    test_benchmark_query()
    test_year_backtest()
    test_single_stock_query()
