import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
from data_svc.storage.lancedb_reader import get_lancedb_reader

r = get_lancedb_reader()

# 检查不同日期的数据
dates_to_check = ['2026-04-17', '2026-04-16', '2026-04-10', '2026-04-01', '2026-03-01', '2026-01-01']

for date in dates_to_check:
    df = r.read(None, date, date, fields=[
        'stock_code', 'trade_date', 'close', 'volume', 'amount', 'change_pct'
    ])
    print(f"\n日期 {date}:")
    print(f"  行数: {len(df)}")
    if not df.is_empty():
        # 检查非null的记录
        non_null_volume = df.filter(pl.col('volume').is_not_null()).height
        non_null_change = df.filter(pl.col('change_pct').is_not_null()).height
        print(f"  volume 非空: {non_null_volume}")
        print(f"  change_pct 非空: {non_null_change}")
        if non_null_volume > 0:
            print(f"  volume 示例: {df.filter(pl.col('volume').is_not_null())['volume'].head(3).to_list()}")
            print(f"  change_pct 示例: {df.filter(pl.col('change_pct').is_not_null())['change_pct'].head(3).to_list()}")