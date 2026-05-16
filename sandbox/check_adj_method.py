"""
检查价格是否需要复权处理

聚宽使用的是"动态复权"：
- 以当前日期为基准，向前复权
- 这样历史价格会随着时间变化

我们的数据可能是：
1. 原始价格（需要复权）
2. 已经复权的价格（不需要处理）

检查方法：
- 找到有除权除息的日期，看价格是否跳变
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def check_price_adjustment():
    print("检查价格复权情况...")
    
    daily_path = Path("data/parquet_data/stock_daily.parquet")
    df = pl.read_parquet(daily_path)
    
    # 选择一只经常分红的股票：000001.SZ（平安银行）
    df_sample = df.filter(pl.col('ts_code') == '000001.SZ').sort('trade_date')
    
    # 查看2023年的数据
    df_2023 = df_sample.filter(
        (pl.col('trade_date') >= '2023-01-01') &
        (pl.col('trade_date') <= '2023-12-31')
    )
    
    print("\n000001.SZ 2023年数据:")
    print(df_2023.select(['trade_date', 'open', 'close', 'adj_factor']))
    
    # 计算adj_factor的变化（找除权除息日）
    df_2023 = df_2023.with_columns(
        pl.col('adj_factor').diff().alias('adj_diff')
    )
    
    # 找adj_factor变化的日期（除权除息日）
    adj_changes = df_2023.filter(pl.col('adj_diff') != 0)
    print(f"\n2023年除权除息日（adj_factor变化）:")
    print(adj_changes.select(['trade_date', 'close', 'adj_factor', 'adj_diff']))
    
    # 检查价格是否在除权日跳变
    if len(adj_changes) > 0:
        print("\n检查除权日前后价格变化:")
        for row in adj_changes.iter_rows(named=True):
            date = row['trade_date']
            # 获取前后两天的数据
            nearby = df_2023.filter(
                (pl.col('trade_date') >= date) &
                (pl.col('trade_date') <= date)
            ).head(2)
            print(f"\n{date}:")
            print(nearby.select(['trade_date', 'close', 'adj_factor']))
    
    # 对比：不复权 vs 复权
    print("\n\n=== 复权方式对比 ===")
    
    # 方式1：不复权（直接用原始价格）
    print("\n方式1：原始价格（不复权）:")
    print(df_2023.select(['trade_date', 'close']).head(10))
    
    # 方式2：绝对复权（原始价格 * adj_factor）
    df_abs_adj = df_2023.with_columns(
        (pl.col('close') * pl.col('adj_factor')).alias('close_adj_abs')
    )
    print("\n方式2：绝对复权（close * adj_factor）:")
    print(df_abs_adj.select(['trade_date', 'close', 'adj_factor', 'close_adj_abs']).head(10))
    
    # 方式3：相对复权（以最后一天为基准）
    last_adj = df_2023['adj_factor'].last()
    df_rel_adj = df_2023.with_columns(
        (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj_rel')
    )
    print(f"\n方式3：相对复权（close * adj_factor / {last_adj:.4f}）:")
    print(df_rel_adj.select(['trade_date', 'close', 'adj_factor', 'close_adj_rel']).head(10))

if __name__ == "__main__":
    check_price_adjustment()
