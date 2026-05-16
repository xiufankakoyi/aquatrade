"""
对比聚宽和本地数据的价格差异

聚宽000001.SZ 2023年1月数据（从用户提供的聚宽代码推断）：
- 2023-01-03: 收盘 13.77
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def compare_price_data():
    print("对比价格数据...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 检查000001.SZ 2023年1月数据
    df_sample = df.filter(
        (pl.col('ts_code') == '000001.SZ') &
        (pl.col('trade_date') >= '2023-01-01') &
        (pl.col('trade_date') <= '2023-01-31')
    ).sort('trade_date')
    
    print("\n000001.SZ 2023年1月收盘价:")
    for row in df_sample.iter_rows(named=True):
        print(f"  {row['trade_date']}: {row['close']:.2f}")
    
    # 检查数据来源
    print("\n检查数据来源...")
    print(f"  数据总行数: {len(df)}")
    print(f"  股票数量: {df['ts_code'].n_unique()}")
    print(f"  日期范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
    
    # 检查是否有复权问题
    print("\n检查复权因子:")
    df_sample = df_sample.with_columns(
        (pl.col('close') * pl.col('adj_factor') / pl.col('adj_factor').last()).alias('close_adj_rel')
    )
    print(df_sample.select(['trade_date', 'close', 'adj_factor', 'close_adj_rel']))

if __name__ == "__main__":
    compare_price_data()
