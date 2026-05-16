"""
检查stock_daily中是否有每日ST状态
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_daily_st():
    print("检查stock_daily中的ST状态...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    print(f"\n列: {df.columns}")
    
    # 检查000040的历史数据
    df_000040 = df.filter(
        pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '') == '000040'
    ).sort('trade_date')
    
    print(f"\n000040 数据行数: {len(df_000040)}")
    
    # 检查是否有is_st列
    if 'is_st' in df.columns:
        print("\n有is_st列！")
        print(df_000040.select(['trade_date', 'close', 'is_st']).tail(30))
    else:
        print("\n没有is_st列")
    
    # 检查stock_info表的结构
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    
    print(f"\nstock_info列: {df_info.columns}")
    print(f"\nstock_info行数: {len(df_info)}")
    
    # 检查stock_info是否有日期字段
    if 'trade_date' in df_info.columns:
        print("\nstock_info有trade_date列，可能是每日数据")
    else:
        print("\nstock_info没有trade_date列，是静态数据")

if __name__ == "__main__":
    check_daily_st()
