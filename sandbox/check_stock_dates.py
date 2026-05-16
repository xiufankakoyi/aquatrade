"""
检查股票数据日期范围
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_stock_dates():
    """检查股票数据日期范围"""
    parquet_path = Path('data/parquet_data/stock_daily.parquet')
    
    if not parquet_path.exists():
        print(f"文件不存在: {parquet_path}")
        return
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 检查日期范围
    date_range = lazy_df.select([
        pl.col('trade_date').min().alias('min_date'),
        pl.col('trade_date').max().alias('max_date')
    ]).collect()
    
    print("=" * 70)
    print("股票数据日期范围")
    print("=" * 70)
    
    print(f"\n最小日期: {date_range['min_date'][0]}")
    print(f"最大日期: {date_range['max_date'][0]}")
    
    # 检查最新日期的数据量
    max_date = date_range['max_date'][0]
    df_latest = lazy_df.filter(pl.col('trade_date') == max_date).collect()
    
    print(f"\n最新日期 {max_date} 数据量: {len(df_latest)} 行")


if __name__ == '__main__':
    check_stock_dates()
