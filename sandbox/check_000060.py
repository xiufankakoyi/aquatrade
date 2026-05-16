"""
检查000060是否应该被过滤
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_000060():
    print("检查000060...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 检查000060在2023-01-03前后的数据
    df_000060 = df.filter(
        (pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '') == '000060') &
        (pl.col('trade_date') >= '2022-12-20') &
        (pl.col('trade_date') <= '2023-01-10')
    ).sort('trade_date')
    
    print("\n000060 数据:")
    print(df_000060.select(['trade_date', 'open', 'close', 'volume']))
    
    # 检查stock_info
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    
    df_000060_info = df_info.filter(
        pl.col('stock_code').cast(pl.Utf8).str.zfill(6) == '000060'
    )
    
    print("\n000060 股票信息:")
    print(df_000060_info)

if __name__ == "__main__":
    check_000060()
