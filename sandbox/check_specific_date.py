"""
检查特定日期的数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from datetime import datetime


def check_specific_date():
    """检查特定日期的数据"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 检查 2025-11-07
    target_dt = datetime.strptime('2025-11-07', '%Y-%m-%d').date()
    
    df = lazy_df.filter(pl.col('trade_date') == target_dt).collect()
    
    print(f"2025-11-07 数据: {len(df)} 行")
    
    if not df.is_empty():
        print(f"stock_code 样本: {df['stock_code'].head(10).to_list()}")
    
    # 检查 2025 年的数据
    df_2025 = lazy_df.filter(
        pl.col('trade_date').dt.year() == 2025
    ).collect()
    
    print(f"\n2025 年数据: {len(df_2025)} 行")
    
    # 检查 2025 年 11 月的数据
    df_2025_11 = lazy_df.filter(
        (pl.col('trade_date').dt.year() == 2025) &
        (pl.col('trade_date').dt.month() == 11)
    ).collect()
    
    print(f"2025 年 11 月数据: {len(df_2025_11)} 行")
    
    if not df_2025_11.is_empty():
        dates = df_2025_11.select('trade_date').unique().sort('trade_date')
        print(f"2025 年 11 月日期: {dates['trade_date'].to_list()}")


if __name__ == '__main__':
    check_specific_date()
