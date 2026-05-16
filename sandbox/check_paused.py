"""
检查停牌数据
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_paused():
    print("检查停牌数据...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 检查2023-01-03是否有所有股票的数据
    df_20230103 = df.filter(pl.col('trade_date') == '2023-01-03')
    
    print(f"\n2023-01-03 数据行数: {len(df_20230103)}")
    print(f"股票数量: {df_20230103['ts_code'].n_unique()}")
    
    # 检查000060是否在2023-01-03有数据
    df_000060 = df_20230103.filter(
        pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '') == '000060'
    )
    
    print(f"\n000060 在 2023-01-03 有数据: {len(df_000060) > 0}")
    
    # 检查volume是否为0（停牌标志）
    if len(df_000060) > 0:
        print(f"  volume: {df_000060['volume'][0]}")
        print(f"  停牌: {df_000060['volume'][0] == 0}")
    
    # 检查所有股票在2023-01-03的volume分布
    print(f"\n2023-01-03 volume分布:")
    print(df_20230103.select('volume').describe())
    
    # 检查volume=0的股票（可能是停牌）
    zero_vol = df_20230103.filter(pl.col('volume') == 0)
    print(f"\nvolume=0的股票数: {len(zero_vol)}")
    if len(zero_vol) > 0:
        print(f"示例:")
        print(zero_vol.head(5).select(['ts_code', 'trade_date', 'open', 'close', 'volume']))

if __name__ == "__main__":
    check_paused()
