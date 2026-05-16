import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
from data_svc.storage.lancedb_reader import get_lancedb_reader

r = get_lancedb_reader()
# 读取最新日期的数据，看看 change_pct 和 volume 的真实情况
df = r.read(None, '2026-04-17', '2026-04-17', fields=[
    'stock_code', 'trade_date', 'open', 'high', 'low', 'close',
    'volume', 'amount', 'change_pct', 'turnover_rate'
])
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\n前5行数据:")
print(df.head(5).to_dicts())

print(f"\nvolume 列的 null 数量: {df['volume'].null_count}")
print(f"change_pct 列的 null 数量: {df['change_pct'].null_count}")
print(f"amount 列的 null 数量: {df['amount'].null_count}")

# 看看最新的一条数据的详情
print("\n第一条数据详情:")
row = df.head(1)
for col in row.columns:
    print(f"  {col}: {row[col][0]}")