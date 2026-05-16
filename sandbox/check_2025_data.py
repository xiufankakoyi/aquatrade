"""
检查 2025 年因子数据完整性
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_2025_data():
    """检查 2025 年因子数据完整性"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 筛选 2025 年数据
    df_2025 = lazy_df.filter(
        pl.col('trade_date').dt.year() == 2025
    ).group_by('trade_date').agg([
        pl.col('ma5').null_count().alias('ma5_null'),
        pl.col('ma10').null_count().alias('ma10_null'),
        pl.col('ma20').null_count().alias('ma20_null'),
        pl.col('ma60').null_count().alias('ma60_null'),
        pl.len().alias('total')
    ]).sort('trade_date', descending=True).collect()
    
    print("=" * 70)
    print("2025 年因子数据完整性统计")
    print("=" * 70)
    
    print("\n最近 20 天数据:")
    for row in df_2025.head(20).iter_rows(named=True):
        date = row['trade_date']
        total = row['total']
        ma20_null = row['ma20_null']
        ma60_null = row['ma60_null']
        
        ma20_valid = total - ma20_null
        ma60_valid = total - ma60_null
        
        status = "✅" if ma20_valid > 1000 else "❌"
        print(f"  {date}: {total} 只股票, MA20有效={ma20_valid}, MA60有效={ma60_valid} {status}")


if __name__ == '__main__':
    check_2025_data()
