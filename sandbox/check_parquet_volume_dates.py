import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
import os

# 直接检查 Parquet 文件中每个日期的 volume 情况
parquet_path = 'C:/Users/Liu/Desktop/projects/aquatrade/data/parquet_data/stock_daily.parquet'

# 读取所有唯一的 trade_date
df_dates = pl.scan_parquet(parquet_path).select(['trade_date', 'volume']).collect()

print(f"Parquet 总行数: {len(df_dates)}")
print(f"唯一日期数: {df_dates['trade_date'].n_unique()}")

# 按日期分组，看每个日期的 null volume 数量
grouped = df_dates.group_by('trade_date').agg([
    pl.count().alias('total'),
    pl.col('volume').filter(pl.col('volume').is_null()).count().alias('null_volume')
]).sort('trade_date', descending=True)

# 找最新一个有 volume 数据的日期
has_volume = grouped.filter(pl.col('null_volume') < pl.col('total'))
print(f"\n有 volume 数据的日期数: {len(has_volume)}")
if has_volume.height > 0:
    latest_with_volume = has_volume['trade_date'][0]
    print(f"最新有 volume 数据的日期: {latest_with_volume}")

print(f"\n最近20个日期的 volume 情况:")
print(grouped.head(20).to_string())