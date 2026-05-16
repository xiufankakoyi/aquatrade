import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
import os

# 检查 Parquet 数据的日期情况
parquet_path = os.path.join('C:/Users/Liu/Desktop/projects/aquatrade', 'data', 'parquet_data', 'stock_daily.parquet')
if os.path.exists(parquet_path):
    print(f"Parquet 文件存在: {parquet_path}")
    # 只读 trade_date 列
    df = pl.scan_parquet(parquet_path).select(['trade_date', 'stock_code', 'volume', 'change_pct']).collect()
    print(f"Parquet 总行数: {len(df)}")
    print(f"列: {list(df.columns)}")

    # 找最新有数据的日期
    non_null = df.filter(pl.col('volume').is_not_null())
    if non_null.height > 0:
        dates = non_null['trade_date'].unique().sort()
        print(f"\nParquet 中 volume 非空的最新日期: {dates.max()}")
        print(f"Parquet 中 volume 非空的日期范围: {dates.min()} ~ {dates.max()}")
        print(f"最近10个有 volume 数据的日期: {dates[-10:].to_list()}")
else:
    print(f"Parquet 文件不存在: {parquet_path}")

# 检查 factor parquet
factor_path = os.path.join('C:/Users/Liu/Desktop/projects/aquatrade', 'data', 'parquet_data', 'factors_momentum_hot.parquet')
if os.path.exists(factor_path):
    print(f"\nFactor Parquet 文件存在: {factor_path}")
    df_factor = pl.scan_parquet(factor_path).select(['trade_date']).collect()
    dates = df_factor['trade_date'].unique().sort()
    print(f"Factor 日期范围: {dates.min()} ~ {dates.max()}")
    print(f"最近10个日期: {dates[-10:].to_list()}")
else:
    print(f"\nFactor Parquet 文件不存在: {factor_path}")