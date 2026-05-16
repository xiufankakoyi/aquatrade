"""
测试 Parquet 加载
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl

parquet_dir = r"c:\Users\Liu\Desktop\projects\aquatrade\data\parquet_data"
stock_daily_path = f"{parquet_dir}/stock_daily.parquet"

print(f"加载: {stock_daily_path}")

# 测试不同日期范围
test_dates = [
    ('1992-12-09', '1992-12-22'),
    ('2025-06-01', '2025-06-30'),
    ('2025-11-01', '2025-11-30'),
]

for start_date, end_date in test_dates:
    print(f"\n测试日期范围: {start_date} ~ {end_date}")
    
    df = pl.scan_parquet(stock_daily_path).filter(
        (pl.col('trade_date') >= start_date) & 
        (pl.col('trade_date') <= end_date) &
        (pl.col('total_mv').is_not_null()) &
        (pl.col('volume') > 0) &
        (pl.col('close').is_not_null())
    ).collect()
    
    print(f"  结果: {len(df)} 行")
    
    if len(df) > 0:
        print(f"  stock_code 示例: {df['stock_code'].unique()[:5].to_list()}")
        print(f"  trade_date 示例: {df['trade_date'].unique()[:5].to_list()}")
