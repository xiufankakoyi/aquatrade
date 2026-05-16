"""
高性能增量更新脚本 v4

目标：每日增量更新 < 1分钟

优化策略：
1. 使用 ArcticDB 私有 API _nvs.batch_write 直接写入 Arrow Table
2. 批量获取数据减少 API 调用
3. 零拷贝写入
"""
from pathlib import Path
import polars as pl
from arcticdb import Arctic
from datetime import datetime, timedelta
import tushare as ts
import time
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import Config

ARCTIC_PATH = project_root / 'data' / 'arctic_db'


def get_arctic_lib(lib_name: str) -> tuple:
    lib_path = ARCTIC_PATH / lib_name
    lib_path.mkdir(parents=True, exist_ok=True)
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    
    existing = arctic.list_libraries()
    if lib_name not in existing:
        arctic.create_library(lib_name)
    
    return arctic, arctic[lib_name]


def get_last_trade_date(lib) -> str:
    try:
        symbols = lib.list_symbols()
        if not symbols:
            return None
        item = lib.read(symbols[0])
        df = pl.from_arrow(item.data)
        if 'trade_date' in df.columns:
            max_date = df['trade_date'].max()
            if hasattr(max_date, 'strftime'):
                return max_date.strftime('%Y%m%d')
            return str(max_date)[:10].replace('-', '')
        return None
    except:
        return None


def batch_write_arrow(lib, symbols: list, data_list: list, metadata_list: list = None):
    """批量写入 Arrow Table（零拷贝）"""
    lib._nvs.batch_write(symbols, data_vector=data_list, metadata_vector=metadata_list)


def update_stock_daily_fast(pro) -> dict:
    """快速更新股票日线数据 - 使用批量写入"""
    print('\n[stock_daily] 更新日线数据...')
    start_time = time.time()
    
    arctic, lib = get_arctic_lib('stock_daily')
    
    last_date = get_last_trade_date(lib)
    if last_date:
        start_date = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
    else:
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
    
    end_date = datetime.now().strftime('%Y%m%d')
    
    if start_date > end_date:
        print(f'  已是最新，跳过')
        return {'updated': 0, 'time': 0}
    
    print(f'  日期范围: {start_date} ~ {end_date}')
    
    cal = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
    if cal is None or cal.empty:
        print(f'  无交易日')
        return {'updated': 0, 'time': 0}
    
    trade_dates = cal[cal['is_open'] == 1]['cal_date'].tolist()
    print(f'  需要更新 {len(trade_dates)} 个交易日')
    
    total_rows = 0
    
    for trade_date in trade_dates:
        try:
            df_daily = pro.daily(trade_date=trade_date)
            if df_daily is None or df_daily.empty:
                continue
            
            df_basic = pro.daily_basic(trade_date=trade_date)
            
            pl_daily = pl.from_pandas(df_daily)
            
            if df_basic is not None and not df_basic.empty:
                pl_basic = pl.from_pandas(df_basic)
                pl_data = pl_daily.join(pl_basic, on='ts_code', how='left', suffix='_basic')
            else:
                pl_data = pl_daily
            
            pl_data = pl_data.with_columns([
                pl.lit(datetime.strptime(trade_date, '%Y%m%d')).alias('trade_date')
            ])
            
            symbols = []
            data_list = []
            
            for ts_code in pl_data['ts_code'].unique().to_list():
                stock_df = pl_data.filter(pl.col('ts_code') == ts_code)
                symbols.append(ts_code)
                data_list.append(stock_df.to_arrow())
            
            if symbols:
                batch_write_arrow(lib, symbols, data_list)
                total_rows += len(symbols)
        
        except Exception as e:
            print(f'  {trade_date} 失败: {e}')
    
    elapsed = time.time() - start_time
    print(f'  完成: {total_rows} 条, 耗时: {elapsed:.1f}s')
    return {'updated': total_rows, 'time': elapsed}


def update_benchmark_fast(pro) -> dict:
    """快速更新指数数据"""
    print('\n[benchmark] 更新指数数据...')
    start_time = time.time()
    
    arctic, lib = get_arctic_lib('benchmark_daily')
    
    indices = ['000001.SH', '399001.SZ', '399006.SZ', '000300.SH', '000905.SH', '000852.SH']
    
    symbols = []
    data_list = []
    
    for index_code in indices:
        try:
            df = pro.index_daily(ts_code=index_code, start_date='20200101')
            if df is not None and not df.empty:
                pl_df = pl.from_pandas(df)
                symbols.append(index_code)
                data_list.append(pl_df.to_arrow())
        except:
            pass
    
    if symbols:
        batch_write_arrow(lib, symbols, data_list)
    
    elapsed = time.time() - start_time
    print(f'  完成: {len(symbols)} 指数, 耗时: {elapsed:.1f}s')
    return {'updated': len(symbols), 'time': elapsed}


def update_stock_basic_fast(pro) -> dict:
    """快速更新股票基本信息"""
    print('\n[stock_basic] 更新股票基本信息...')
    start_time = time.time()
    
    arctic, lib = get_arctic_lib('stock_basic')
    
    try:
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        if df is not None and not df.empty:
            pl_df = pl.from_pandas(df)
            lib._nvs.write('stock_basic', pl_df.to_arrow())
            elapsed = time.time() - start_time
            print(f'  完成: {len(pl_df)} 条, 耗时: {elapsed:.1f}s')
            return {'updated': len(pl_df), 'time': elapsed}
    except Exception as e:
        print(f'  失败: {e}')
    
    return {'updated': 0, 'time': 0}


def run_fast_update():
    """运行快速增量更新"""
    print('=' * 70)
    print('AquaTrade 快速增量更新 v4（Arrow 批量写入）')
    print('=' * 70)
    print(f'开始时间: {datetime.now()}')
    
    total_start = time.time()
    
    pro = ts.pro_api(Config.TUSHARE_TOKEN)
    
    results = {}
    results['stock_daily'] = update_stock_daily_fast(pro)
    results['benchmark'] = update_benchmark_fast(pro)
    results['stock_basic'] = update_stock_basic_fast(pro)
    
    total_elapsed = time.time() - total_start
    
    print('\n' + '=' * 70)
    print('更新完成')
    print('=' * 70)
    print(f'总耗时: {total_elapsed:.1f}s')
    for name, result in results.items():
        print(f'  {name}: {result["updated"]} 条, {result["time"]:.1f}s')
    
    return results


if __name__ == '__main__':
    run_fast_update()
