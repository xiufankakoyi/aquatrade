"""
检查基准指数数据是否正确
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library

def check_index_data():
    print("=" * 70)
    print("检查指数数据")
    print("=" * 70)
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    arctic = get_arctic_instance_for_library('market_data')
    lib = arctic['market_data']
    
    indices = [
        ('000001.SH', '上证指数'),
        ('000852.SH', '中证1000'),
        ('000300.SH', '沪深300'),
        ('000905.SH', '中证500'),
    ]
    
    for ts_code, name in indices:
        if ts_code not in lib.list_symbols():
            print(f"{name}({ts_code}): 数据不存在")
            continue
        
        item = lib.read(ts_code, date_range=(pd.Timestamp(start_date), pd.Timestamp(end_date)))
        df = item.data
        
        if df.empty:
            print(f"{name}({ts_code}): 数据为空")
            continue
        
        df = df.sort_index()
        
        first_close = df['close'].iloc[0]
        last_close = df['close'].iloc[-1]
        total_return = (last_close - first_close) / first_close * 100
        
        print(f"\n{name}({ts_code}):")
        print(f"  数据范围: {df.index[0].date()} 到 {df.index[-1].date()}")
        print(f"  数据点数: {len(df)}")
        print(f"  起始价格: {first_close:.2f}")
        print(f"  结束价格: {last_close:.2f}")
        print(f"  总收益: {total_return:.2f}%")


if __name__ == "__main__":
    check_index_data()
