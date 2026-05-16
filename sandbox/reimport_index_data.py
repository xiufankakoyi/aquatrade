"""
删除损坏的指数库并重新导入
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


def delete_corrupted_libraries():
    """删除损坏的库"""
    base_path = Path('data/arctic_db')
    
    # 需要重建的库（排除 hs300_daily 因为它是正常的）
    libs_to_rebuild = ['sz50_daily', 'zz500_daily', 'cyb_index_daily', 
                       'sh_index_daily', 'sz_index_daily']
    
    print("=" * 70)
    print("删除损坏的库")
    print("=" * 70)
    
    for lib_name in libs_to_rebuild:
        lib_path = base_path / lib_name
        if lib_path.exists():
            print(f"删除: {lib_path}")
            shutil.rmtree(lib_path)


def import_index_direct():
    """直接使用 ArcticDB 导入指数数据"""
    marketdata_dir = Path('data/marketdata')
    base_path = Path('data/arctic_db')
    
    print("\n" + "=" * 70)
    print("导入指数数据")
    print("=" * 70)
    
    for csv_file, config in INDEX_MAPPING.items():
        file_path = marketdata_dir / csv_file
        
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            continue
        
        lib_name = config['library']
        symbol = config['symbol']
        
        # 检查是否已经存在且正常
        lib_path = base_path / lib_name
        if lib_path.exists():
            try:
                arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
                lib = arctic[lib_name]
                symbols = lib.list_symbols()
                if symbol in symbols:
                    data = lib.read(symbol)
                    print(f"✅ {config['name']}: 已存在 {len(data.data)} 行")
                    continue
            except:
                # 如果读取失败，删除重建
                print(f"删除损坏的库: {lib_name}")
                shutil.rmtree(lib_path)
        
        # 创建新库并导入数据
        print(f"\n导入: {config['name']}")
        
        try:
            df = read_index_csv(file_path)
            print(f"  读取 {len(df)} 行")
            
            # 创建库目录
            lib_path.mkdir(parents=True, exist_ok=True)
            
            # 创建 Arctic 实例
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            
            # 创建库
            arctic.create_library(lib_name)
            lib = arctic[lib_name]
            
            # 使用 Arrow Table 写入
            table = pa.Table.from_pandas(df)
            lib._nvs.write(symbol, table)
            
            print(f"  ✅ 写入成功")
            
        except Exception as e:
            print(f"  ❌ 导入失败: {e}")
            import traceback
            traceback.print_exc()


def verify_all():
    """验证所有数据"""
    base_path = Path('data/arctic_db')
    
    print("\n" + "=" * 70)
    print("验证导入结果")
    print("=" * 70)
    
    for csv_file, config in INDEX_MAPPING.items():
        lib_name = config['library']
        symbol = config['symbol']
        
        lib_path = base_path / lib_name
        if not lib_path.exists():
            print(f"❌ {config['name']}: 目录不存在")
            continue
        
        try:
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            lib = arctic[lib_name]
            data = lib.read(symbol)
            print(f"✅ {config['name']}: {len(data.data)} 行")
        except Exception as e:
            print(f"❌ {config['name']}: {e}")


if __name__ == '__main__':
    delete_corrupted_libraries()
    import_index_direct()
    verify_all()
