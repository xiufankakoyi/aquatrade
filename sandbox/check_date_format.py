"""
检查 Parquet 日期格式
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from datetime import datetime


def check_date_format():
    """检查日期格式"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    schema = lazy_df.collect_schema()
    
    print("=" * 70)
    print("检查 Parquet 日期格式")
    print("=" * 70)
    
    print(f"\nSchema:")
    for col, dtype in schema.items():
        print(f"  {col}: {dtype}")
    
    # 读取样本数据
    sample = lazy_df.head(10).collect()
    
    print(f"\n样本数据 (前10行):")
    for row in sample.iter_rows(named=True):
        print(f"  trade_date={row['trade_date']}, type={type(row['trade_date'])}")
    
    # 检查日期范围
    date_range = lazy_df.select([
        pl.col('trade_date').min().alias('min_date'),
        pl.col('trade_date').max().alias('max_date')
    ]).collect()
    
    print(f"\n日期范围:")
    print(f"  最小: {date_range['min_date'][0]}")
    print(f"  最大: {date_range['max_date'][0]}")
    
    # 尝试筛选
    target_date = '2025-11-07'
    target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    print(f"\n筛选目标日期: {target_date} ({target_dt})")
    
    # 按字符串筛选
    str_filter = lazy_df.filter(pl.col('trade_date') == target_date).collect()
    print(f"  字符串筛选: {len(str_filter)} 行")
    
    # 按 date 筛选
    date_filter = lazy_df.filter(pl.col('trade_date') == target_dt).collect()
    print(f"  date 筛选: {len(date_filter)} 行")
    
    # 按字符串包含筛选
    str_contains = lazy_df.filter(pl.col('trade_date').cast(pl.String).str.contains('2025-11-07')).collect()
    print(f"  字符串包含筛选: {len(str_contains)} 行")


if __name__ == '__main__':
    check_date_format()
