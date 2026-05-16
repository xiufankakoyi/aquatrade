"""
使用完全独立的 Arctic 实例导入指数数据
每个库使用完全独立的目录，不共享任何配置
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import shutil
import pandas as pd
from loguru import logger
from arcticdb import Arctic
import pyarrow as pa
import os


INDEX_MAPPING = {
    '沪深300.csv': {
        'library': 'hs300_daily',
        'symbol': 'hs300',
        'code': '000300.SH',
        'name': '沪深300'
    },
    '上证50.csv': {
        'library': 'sz50_daily',
        'symbol': 'sz50',
        'code': '000016.SH',
        'name': '上证50'
    },
    '中证500.csv': {
        'library': 'zz500_daily',
        'symbol': 'zz500',
        'code': '000905.SH',
        'name': '中证500'
    },
    '创业板指数数据.csv': {
        'library': 'cyb_index_daily',
        'symbol': 'cyb_index',
        'code': '399006.SZ',
        'name': '创业板指'
    },
    '上证指数数据.csv': {
        'library': 'sh_index_daily',
        'symbol': 'sh_index',
        'code': '000001.SH',
        'name': '上证指数'
    },
    '深证成指数据.csv': {
        'library': 'sz_index_daily',
        'symbol': 'sz_index',
        'code': '399001.SZ',
        'name': '深证成指'
    },
}


def read_index_csv(file_path: Path) -> pd.DataFrame:
    """读取指数 CSV 文件"""
    df = pd.read_csv(file_path, encoding='utf-8')
    
    column_mapping = {
        '交易日期': 'trade_date',
        '开盘价': 'open',
        '最高价': 'high',
        '最低价': 'low',
        '收盘价': 'close',
        '前收盘价': 'pre_close',
        '涨跌额': 'change',
        '涨跌幅(%)': 'pct_chg',
        '成交量(手)': 'volume',
        '成交额(万元)': 'amount',
        '股票代码': 'ts_code',
    }
    
    df = df.rename(columns=column_mapping)
    
    if 'trade_date' in df.columns:
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        elif df['trade_date'].dtype == 'int64':
            df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str), format='%Y%m%d')
    
    df = df.sort_values('trade_date')
    
    if 'trade_date' in df.columns:
        df = df.set_index('trade_date')
    
    return df


def clean_all_index_libs():
    """清理所有指数库"""
    base_path = Path('data/arctic_db')
    
    print("=" * 70)
    print("清理所有指数库")
    print("=" * 70)
    
    for csv_file, config in INDEX_MAPPING.items():
        lib_name = config['library']
        lib_path = base_path / lib_name
        
        if lib_path.exists():
            print(f"删除: {lib_path}")
            shutil.rmtree(lib_path)


def import_to_single_lib():
    """将所有指数数据导入到单个库中"""
    marketdata_dir = Path('data/marketdata')
    base_path = Path('data/arctic_db')
    
    # 使用一个统一的库存储所有指数
    lib_name = 'index_daily'
    lib_path = base_path / lib_name
    
    print("\n" + "=" * 70)
    print(f"导入所有指数数据到单一库: {lib_name}")
    print("=" * 70)
    
    # 删除旧库
    if lib_path.exists():
        print(f"删除旧库: {lib_path}")
        shutil.rmtree(lib_path)
    
    # 创建库目录
    lib_path.mkdir(parents=True, exist_ok=True)
    
    # 创建 Arctic 实例
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    
    # 创建库
    try:
        arctic.create_library(lib_name)
    except Exception as e:
        print(f"创建库失败: {e}")
        return
    
    lib = arctic[lib_name]
    
    # 导入每个指数
    for csv_file, config in INDEX_MAPPING.items():
        file_path = marketdata_dir / csv_file
        
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            continue
        
        symbol = config['symbol']
        
        try:
            df = read_index_csv(file_path)
            print(f"\n导入 {config['name']}: {len(df)} 行")
            
            # 使用 Arrow Table 写入
            table = pa.Table.from_pandas(df)
            lib._nvs.write(symbol, table)
            
            print(f"  ✅ 写入成功")
            
        except Exception as e:
            print(f"  ❌ 导入失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 验证
    print("\n" + "=" * 70)
    print("验证导入结果")
    print("=" * 70)
    
    symbols = lib.list_symbols()
    print(f"库中的 symbols: {symbols}")
    
    for csv_file, config in INDEX_MAPPING.items():
        symbol = config['symbol']
        if symbol in symbols:
            try:
                data = lib.read(symbol)
                print(f"✅ {config['name']}: {len(data.data)} 行")
            except Exception as e:
                print(f"❌ {config['name']}: {e}")


if __name__ == '__main__':
    clean_all_index_libs()
    import_to_single_lib()
