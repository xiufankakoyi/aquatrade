"""
检查000060是否涨跌停
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_000060_limit():
    print("检查000060涨跌停...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 检查000060在2023-01-03的数据
    df_000060 = df.filter(
        (pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '') == '000060') &
        (pl.col('trade_date') == '2023-01-03')
    )
    
    print("\n000060 2023-01-03 数据:")
    print(df_000060.select(['trade_date', 'open', 'close', 'high', 'low', 'limit_up', 'limit_down', 'volume']))
    
    # 检查是否涨停
    if len(df_000060) > 0:
        row = df_000060.row(0, named=True)
        print(f"\n涨停价: {row['limit_up']}")
        print(f"跌停价: {row['limit_down']}")
        print(f"开盘价: {row['open']}")
        print(f"收盘价: {row['close']}")
        
        if row['open'] >= row['limit_up'] * 0.99:  # 接近涨停
            print("\n⚠️ 开盘价接近涨停，可能无法买入")
    
    # 对比000021
    df_000021 = df.filter(
        (pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '') == '000021') &
        (pl.col('trade_date') == '2023-01-03')
    )
    
    print("\n000021 2023-01-03 数据:")
    print(df_000021.select(['trade_date', 'open', 'close', 'high', 'low', 'limit_up', 'limit_down', 'volume']))

if __name__ == "__main__":
    check_000060_limit()
