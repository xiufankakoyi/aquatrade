"""
检查 ArcticDB factor 库中是否有历史数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def check_historical_data():
    """检查是否有历史数据"""
    print("=" * 70)
    print("检查 ArcticDB factor 库历史数据")
    print("=" * 70)
    
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    
    symbols = lib.list_symbols()
    print(f"Symbol 数量: {len(symbols)}")
    
    # 检查几个 symbol 的数据
    checked = 0
    for symbol in symbols:
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        if len(df) > 100:  # 只检查数据量大的
            print(f"\n检查 symbol: {symbol}")
            print(f"  行数: {len(df)}")
            print(f"  日期范围: {df.index.min()} ~ {df.index.max()}")
            
            checked += 1
            if checked >= 5:
                break


if __name__ == '__main__':
    check_historical_data()
