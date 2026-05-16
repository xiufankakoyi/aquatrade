"""
使用不同方式读取 ArcticDB 数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
import pyarrow as pa


def read_with_arrow_direct():
    """直接使用 _nvs 读取"""
    from arcticdb import Arctic
    
    index_libs = [
        ('hs300_daily', 'hs300', '沪深300'),
        ('sz50_daily', 'sz50', '上证50'),
        ('zz500_daily', 'zz500', '中证500'),
    ]
    
    print("=" * 70)
    print("使用 _nvs 直接读取")
    print("=" * 70)
    
    for lib_name, symbol, display_name in index_libs:
        try:
            lib_path = f"data/arctic_db/{lib_name}"
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            lib = arctic[lib_name]
            
            # 尝试使用 _nvs 读取
            vit = lib._nvs.read(symbol)
            table = vit.table
            
            print(f"\n✅ {display_name}:")
            print(f"   行数: {table.num_rows}")
            print(f"   列: {table.column_names[:5]}...")
            
        except Exception as e:
            print(f"\n❌ {display_name}: {e}")


def read_with_regular_api():
    """使用常规 API 读取"""
    from arcticdb import Arctic
    
    index_libs = [
        ('hs300_daily', 'hs300', '沪深300'),
        ('sz50_daily', 'sz50', '上证50'),
        ('zz500_daily', 'zz500', '中证500'),
    ]
    
    print("\n" + "=" * 70)
    print("使用常规 API 读取")
    print("=" * 70)
    
    for lib_name, symbol, display_name in index_libs:
        try:
            lib_path = f"data/arctic_db/{lib_name}"
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            lib = arctic[lib_name]
            
            # 使用 read 方法
            data = lib.read(symbol)
            df = data.data
            
            print(f"\n✅ {display_name}:")
            print(f"   行数: {len(df)}")
            print(f"   类型: {type(df)}")
            
        except Exception as e:
            print(f"\n❌ {display_name}: {e}")
            import traceback
            traceback.print_exc()


def check_symbols():
    """检查库中的 symbols"""
    from arcticdb import Arctic
    
    index_libs = ['hs300_daily', 'sz50_daily', 'zz500_daily']
    
    print("\n" + "=" * 70)
    print("检查库中的 symbols")
    print("=" * 70)
    
    for lib_name in index_libs:
        try:
            lib_path = f"data/arctic_db/{lib_name}"
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            lib = arctic[lib_name]
            
            symbols = lib.list_symbols()
            print(f"\n{lib_name}: {symbols}")
            
        except Exception as e:
            print(f"\n❌ {lib_name}: {e}")


if __name__ == '__main__':
    check_symbols()
    read_with_arrow_direct()
    read_with_regular_api()
