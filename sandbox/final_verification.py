"""
最终数据完整性验证
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
from arcticdb import Arctic


def verify_all_libraries():
    """验证所有 ArcticDB 库"""
    base_path = Path('data/arctic_db')
    
    print("=" * 70)
    print("ArcticDB 数据完整性最终验证")
    print("=" * 70)
    
    # 定义所有库
    libraries = {
        'stock_daily': {'symbols': 'auto', 'name': '股票日线'},
        'factor': {'symbols': 'auto', 'name': '因子数据'},
        'benchmark': {'symbols': 'auto', 'name': '基准数据'},
        'limit_status': {'symbols': 'auto', 'name': '涨跌停状态'},
        'stock_basic': {'symbols': ['stock_basic'], 'name': '股票基础信息'},
        'stock_info': {'symbols': ['stock_info'], 'name': '股票信息'},
        'index_daily': {'symbols': ['hs300', 'sz50', 'zz500', 'cyb_index', 'sh_index', 'sz_index'], 'name': '指数数据'},
    }
    
    results = []
    
    for lib_name, info in libraries.items():
        lib_path = base_path / lib_name
        
        if not lib_path.exists():
            print(f"\n❌ {info['name']} ({lib_name}): 目录不存在")
            results.append({'lib': lib_name, 'status': 'NOT_FOUND'})
            continue
        
        try:
            arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
            libs = arctic.list_libraries()
            
            if lib_name not in libs:
                print(f"\n❌ {info['name']} ({lib_name}): 库不存在")
                results.append({'lib': lib_name, 'status': 'NOT_IN_LIST'})
                continue
            
            lib = arctic[lib_name]
            symbols = lib.list_symbols()
            
            if info['symbols'] == 'auto':
                total_rows = 0
                sample_count = min(5, len(symbols))
                
                for symbol in symbols[:sample_count]:
                    try:
                        data = lib.read(symbol)
                        df = data.data
                        if hasattr(df, 'to_pandas'):
                            df = df.to_pandas()
                        total_rows += len(df)
                    except:
                        pass
                
                avg_rows = total_rows // sample_count if sample_count > 0 else 0
                estimated_total = avg_rows * len(symbols)
                
                print(f"\n✅ {info['name']} ({lib_name}):")
                print(f"   Symbols: {len(symbols)}")
                print(f"   估计总行数: ~{estimated_total:,}")
                results.append({'lib': lib_name, 'status': 'OK', 'symbols': len(symbols)})
            else:
                # 检查特定 symbols
                found = []
                missing = []
                
                for symbol in info['symbols']:
                    if symbol in symbols:
                        data = lib.read(symbol)
                        df = data.data
                        if hasattr(df, 'to_pandas'):
                            df = df.to_pandas()
                        found.append({'symbol': symbol, 'rows': len(df)})
                    else:
                        missing.append(symbol)
                
                if found:
                    print(f"\n✅ {info['name']} ({lib_name}):")
                    for f in found:
                        print(f"   {f['symbol']}: {f['rows']:,} 行")
                    results.append({'lib': lib_name, 'status': 'OK', 'found': len(found)})
                
                if missing:
                    print(f"   ⚠️ 缺失: {missing}")
                    results.append({'lib': lib_name, 'status': 'PARTIAL', 'missing': missing})
            
        except Exception as e:
            print(f"\n❌ {info['name']} ({lib_name}): {e}")
            results.append({'lib': lib_name, 'status': 'ERROR', 'error': str(e)})
    
    # 汇总
    print("\n" + "=" * 70)
    print("验证汇总")
    print("=" * 70)
    
    ok_count = sum(1 for r in results if r['status'] == 'OK')
    error_count = sum(1 for r in results if r['status'] in ['ERROR', 'NOT_FOUND', 'NOT_IN_LIST'])
    
    print(f"\n✅ 正常: {ok_count}")
    print(f"❌ 异常: {error_count}")
    
    if error_count == 0:
        print("\n🎉 所有数据验证通过！")
    else:
        print("\n⚠️ 部分数据存在问题，请检查上述错误信息")


if __name__ == '__main__':
    verify_all_libraries()
