"""
检查有完整因子数据的日期
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_complete_dates():
    """检查有完整因子数据的日期"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 按日期统计 MA20 非 null 数量
    df = lazy_df.group_by('trade_date').agg([
        pl.col('ma5').null_count().alias('ma5_null'),
        pl.col('ma10').null_count().alias('ma10_null'),
        pl.col('ma20').null_count().alias('ma20_null'),
        pl.col('ma60').null_count().alias('ma60_null'),
        pl.len().alias('total')
    ]).sort('trade_date', descending=True).collect()
    
    print("=" * 70)
    print("因子数据完整性统计（按日期）")
    print("=" * 70)
    
    # 只显示最近 30 天
    print("\n最近 30 天数据:")
    for row in df.head(30).iter_rows(named=True):
        date = row['trade_date']
        total = row['total']
        ma20_null = row['ma20_null']
        ma60_null = row['ma60_null']
        
        ma20_valid = total - ma20_null
        ma60_valid = total - ma60_null
        
        status = "✅" if ma20_valid > 1000 else "❌"
        print(f"  {date}: {total} 只股票, MA20有效={ma20_valid}, MA60有效={ma60_valid} {status}")
    
    # 找到最新有完整数据的日期
    complete_dates = df.filter(
        (pl.col('ma20_null') < pl.col('total') * 0.5) &
        (pl.col('ma60_null') < pl.col('total') * 0.5)
    )
    
    if not complete_dates.is_empty():
        latest_complete = complete_dates['trade_date'][0]
        print(f"\n最新有完整 MA 数据的日期: {latest_complete}")


if __name__ == '__main__':
    check_complete_dates()
