import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
from data_svc.storage.lancedb_reader import get_lancedb_reader

r = get_lancedb_reader()

# 读取全量数据，检查 volume 和 change_pct 的整体情况
# 只取 stock_code, trade_date, volume, amount, change_pct
import lancedb
db = lancedb.connect(r.db_path)
tbl = db.open_table('daily_ohlcv')

# 用 scanner 读取一小部分数据测试
scanner = tbl.to_lance().scanner()
arrow_table = scanner.to_table()
df = pl.from_arrow(arrow_table)

print(f"总行数: {len(df)}")
print(f"Columns: {list(df.columns)}")

# 检查 volume 和 change_pct 的 null 比例
total = len(df)
null_volume = df.filter(pl.col('volume').is_null()).height
null_change = df.filter(pl.col('change_pct').is_null()).height
null_amount = df.filter(pl.col('amount').is_null()).height

print(f"\nNull 统计 (总数 {total}):")
print(f"  volume null: {null_volume} ({null_volume/total*100:.2f}%)")
print(f"  change_pct null: {null_change} ({null_change/total*100:.2f}%)")
print(f"  amount null: {null_amount} ({null_amount/total*100:.2f}%)")

# 检查有数据的记录的日期范围
non_null_df = df.filter(pl.col('volume').is_not_null())
if non_null_df.height > 0:
    print(f"\n有 volume 数据的记录数: {non_null_df.height}")
    dates = non_null_df['trade_date'].unique().sort()
    print(f"日期范围: {dates.min()} ~ {dates.max()}")
    print(f"最近5个有数据的日期: {dates[-5:].to_list()}")
else:
    print("\n没有找到任何有 volume 数据的记录!")

# 看看 2024 年的数据
df_2024 = df.filter(pl.col('trade_date') >= pl.date(2024, 1, 1))
print(f"\n2024年以来数据行数: {len(df_2024)}")
null_vol_2024 = df_2024.filter(pl.col('volume').is_null()).height
print(f"2024年 volume null: {null_vol_2024}/{len(df_2024)}")