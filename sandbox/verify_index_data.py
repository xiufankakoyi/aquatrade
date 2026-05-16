"""
验证指数数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


INDEX_LIBS = {
    'hs300_daily': {'symbol': 'hs300', 'name': '沪深300'},
    'sz50_daily': {'symbol': 'sz50', 'name': '上证50'},
    'zz500_daily': {'symbol': 'zz500', 'name': '中证500'},
    'cyb_index_daily': {'symbol': 'cyb_index', 'name': '创业板指'},
    'sh_index_daily': {'symbol': 'sh_index', 'name': '上证指数'},
    'sz_index_daily': {'symbol': 'sz_index', 'name': '深证成指'},
}


def verify_all():
    """验证所有指数数据"""
    print("=" * 70)
    print("验证指数数据")
    print("=" * 70)
    
    for lib_name, info in INDEX_LIBS.items():
        try:
            arctic = get_arctic_instance_for_library(lib_name)
            libs = arctic.list_libraries()
            
            if lib_name not in libs:
                print(f"❌ {info['name']}: 库不存在")
                continue
            
            lib = arctic[lib_name]
            symbols = lib.list_symbols()
            
            if info['symbol'] not in symbols:
                print(f"❌ {info['name']}: symbol 不存在 ({info['symbol']})")
                print(f"   可用 symbols: {symbols}")
                continue
            
            data = lib.read(info['symbol'])
            df = data.data
            
            if hasattr(df, 'to_pandas'):
                df = df.to_pandas()
            
            print(f"✅ {info['name']}: {len(df)} 行")
            print(f"   日期范围: {df.index.min()} ~ {df.index.max()}")
            print(f"   列: {list(df.columns)[:5]}...")
            
        except Exception as e:
            print(f"❌ {info['name']}: {e}")


if __name__ == '__main__':
    verify_all()
