"""
验证 index_daily 库并检查数据完整性
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from arcticdb import Arctic
import pandas as pd


def verify_index_daily():
    """验证 index_daily 库"""
    lib_path = Path('data/arctic_db/index_daily')
    
    print("=" * 70)
    print("验证 index_daily 库")
    print("=" * 70)
    
    arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
    lib = arctic['index_daily']
    
    symbols = lib.list_symbols()
    print(f"\nSymbols: {symbols}")
    
    index_info = {
        'hs300': '沪深300',
        'sz50': '上证50',
        'zz500': '中证500',
        'cyb_index': '创业板指',
        'sh_index': '上证指数',
        'sz_index': '深证成指',
    }
    
    print("\n数据详情:")
    for symbol, name in index_info.items():
        if symbol in symbols:
            data = lib.read(symbol)
            df = data.data
            
            # 转换为 Pandas
            if hasattr(df, 'to_pandas'):
                df = df.to_pandas()
            
            print(f"\n✅ {name} ({symbol}):")
            print(f"   行数: {len(df)}")
            print(f"   日期范围: {df.index.min()} ~ {df.index.max()}")
            print(f"   列: {list(df.columns)[:6]}...")
            
            # 检查是否有 null 值
            null_counts = df.isnull().sum()
            if null_counts.any():
                print(f"   ⚠️ Null 值: {null_counts[null_counts > 0].to_dict()}")
            else:
                print(f"   ✅ 无 null 值")
        else:
            print(f"\n❌ {name} ({symbol}): 不存在")


if __name__ == '__main__':
    verify_index_daily()
