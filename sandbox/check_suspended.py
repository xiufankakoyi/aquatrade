"""
检查停牌数据
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_suspended():
    print("检查停牌数据...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 检查是否有停牌相关字段
    print(f"\n数据列: {df.columns}")
    
    # 检查limit_up, limit_down字段
    if 'limit_up' in df.columns:
        print(f"\nlimit_up示例:")
        print(df.filter(pl.col('limit_up') > 0).select(['trade_date', 'ts_code', 'close', 'limit_up']).head(5))
    
    if 'limit_down' in df.columns:
        print(f"\nlimit_down示例:")
        print(df.filter(pl.col('limit_down') > 0).select(['trade_date', 'ts_code', 'close', 'limit_down']).head(5))
    
    # 检查数据中是否有volume=0的情况（可能是停牌）
    print(f"\nvolume=0的记录数:")
    zero_vol = df.filter(pl.col('volume') == 0)
    print(f"  {len(zero_vol)} 条")
    
    # 检查close为null的情况
    print(f"\nclose为null的记录数:")
    null_close = df.filter(pl.col('close').is_null())
    print(f"  {len(null_close)} 条")
    
    # 检查某只股票的数据连续性
    print(f"\n000001.SZ 2023年1月数据:")
    df_sample = df.filter(
        (pl.col('ts_code') == '000001.SZ') &
        (pl.col('trade_date') >= '2023-01-01') &
        (pl.col('trade_date') <= '2023-01-31')
    ).sort('trade_date')
    print(df_sample.select(['trade_date', 'open', 'close', 'volume']))

if __name__ == "__main__":
    check_suspended()
