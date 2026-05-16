"""
检查因子数据状态
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

def check_stock_daily_factors():
    """检查 stock_daily 中的因子列"""
    print("\n" + "=" * 80)
    print("检查 stock_daily.parquet 中的因子列")
    print("=" * 80)
    
    parquet_path = Path("./data/parquet_data/stock_daily.parquet")
    
    if parquet_path.exists():
        df = pl.scan_parquet(parquet_path)
        schema = df.collect_schema()
        
        factor_cols = ['ma5', 'ma10', 'ma20', 'ma3_avg_price', 'ma5_avg_price', 'ma10_avg_price', 'volume_ma5']
        
        print("\n因子列状态:")
        for col in factor_cols:
            if col in schema.names():
                sample = df.select(col).filter(pl.col(col).is_not_null()).limit(5).collect()
                null_count = df.filter(pl.col(col).is_null()).select(pl.len()).collect().item()
                total_count = df.select(pl.len()).collect().item()
                print(f"  {col}: 存在, 非空率: {(total_count - null_count) / total_count * 100:.1f}%")
            else:
                print(f"  {col}: 不存在")
        
        print(f"\n所有列: {schema.names()}")
    else:
        print(f"文件不存在: {parquet_path}")

def check_factor_parquet():
    """检查因子 Parquet 文件"""
    print("\n" + "=" * 80)
    print("检查因子 Parquet 文件")
    print("=" * 80)
    
    parquet_dir = Path("./data/parquet_data")
    
    files = [
        'factors_momentum_hot.parquet',
        'factors_momentum_archive.parquet',
    ]
    
    for f in files:
        path = parquet_dir / f
        if path.exists():
            df = pl.scan_parquet(path)
            schema = df.collect_schema()
            total = df.select(pl.len()).collect().item()
            
            print(f"\n{f}:")
            print(f"  行数: {total:,}")
            print(f"  列: {schema.names()}")
            
            if 'trade_date' in schema.names():
                dates = df.select([
                    pl.col('trade_date').min().alias('min'),
                    pl.col('trade_date').max().alias('max')
                ]).collect()
                print(f"  日期范围: {dates['min'][0]} ~ {dates['max'][0]}")
        else:
            print(f"\n{f}: 不存在")

def check_arcticdb_factor():
    """检查 ArcticDB 因子库"""
    print("\n" + "=" * 80)
    print("检查 ArcticDB 因子库")
    print("=" * 80)
    
    try:
        import arcticdb as adb
        
        arctic = adb.Arctic("lmdb://./data/arctic_db")
        
        try:
            lib = arctic['factor']
            symbols = lib.list_symbols()
            
            print(f"\n因子库符号数: {len(symbols)}")
            
            for sym in symbols[:10]:
                try:
                    result = lib.read(sym)
                    data = result.data
                    
                    import pyarrow as pa
                    if isinstance(data, pa.Table):
                        rows = len(data)
                    else:
                        rows = len(data)
                    
                    print(f"  - {sym}: {rows} 行")
                except Exception as e:
                    print(f"  - {sym}: 读取失败 {e}")
            
            if len(symbols) > 10:
                print(f"  ... 还有 {len(symbols) - 10} 个符号")
                
        except Exception as e:
            print(f"因子库不存在或读取失败: {e}")
            
    except ImportError:
        print("ArcticDB 未安装")

if __name__ == "__main__":
    check_stock_daily_factors()
    check_factor_parquet()
    check_arcticdb_factor()
