"""
检查000040的ST状态
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_000040_st():
    print("检查000040的ST状态...")
    
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    
    # 检查000040
    df_000040 = df_info.filter(pl.col('stock_code').cast(pl.Utf8).str.zfill(6) == '000040')
    
    print("\n000040 信息:")
    print(df_000040)
    
    # 检查ST股票列表
    st_stocks = df_info.filter(pl.col('is_st') == 1)
    print(f"\nST股票总数: {len(st_stocks)}")
    print(f"\n前10只ST股票:")
    print(st_stocks.head(10))
    
    # 检查stock_name列
    if 'stock_name' in df_info.columns:
        print("\n检查股票名称包含ST的:")
        st_by_name = df_info.filter(pl.col('stock_name').str.contains('ST'))
        print(f"  数量: {len(st_by_name)}")
        print(st_by_name.head(10))

if __name__ == "__main__":
    check_000040_st()
