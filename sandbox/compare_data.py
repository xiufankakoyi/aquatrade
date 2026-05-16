"""
对比 ArcticDB 和 Parquet 中同一股票的数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def compare_data():
    """对比同一股票的数据"""
    print("=" * 70)
    print("对比 ArcticDB 和 Parquet 数据")
    print("=" * 70)
    
    # 从 Parquet 获取一个有 2026 年数据的股票
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 获取一个有 2026 年数据的股票
    df_2026 = lazy_df.filter(pl.col('trade_date').dt.year() == 2026).collect()
    sample_code = df_2026['stock_code'][0]
    
    print(f"\n样本股票: {sample_code}")
    
    # 从 Parquet 获取该股票的所有数据
    parquet_df = lazy_df.filter(pl.col('stock_code') == sample_code).sort('trade_date').collect()
    
    print(f"\nParquet 数据:")
    print(f"  行数: {len(parquet_df)}")
    print(f"  日期范围: {parquet_df['trade_date'][0]} ~ {parquet_df['trade_date'][-1]}")
    
    # 检查 MA 列
    ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
    print("\n  MA 列统计:")
    for col in ma_cols:
        null_count = parquet_df[col].null_count()
        print(f"    {col}: null={null_count}/{len(parquet_df)}")
    
    # 从 ArcticDB 获取该股票的数据
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    
    symbol = f"momentum_{sample_code}"
    
    if symbol in lib.list_symbols():
        data = lib.read(symbol)
        arctic_df = data.data
        
        if hasattr(arctic_df, 'to_pandas'):
            arctic_df = arctic_df.to_pandas()
        
        print(f"\nArcticDB 数据:")
        print(f"  行数: {len(arctic_df)}")
        print(f"  日期范围: {arctic_df.index.min()} ~ {arctic_df.index.max()}")
        
        # 检查 MA 列
        print("\n  MA 列统计:")
        for col in ma_cols:
            if col in arctic_df.columns:
                null_count = arctic_df[col].isna().sum()
                print(f"    {col}: null={null_count}/{len(arctic_df)}")
    else:
        print(f"\nArcticDB 中没有 {symbol}")


if __name__ == '__main__':
    compare_data()
