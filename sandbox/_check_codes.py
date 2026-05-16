import sys
sys.path.insert(0, '.')
import lancedb
import polars as pl

db = lancedb.connect('data/lancedb')
t = db.open_table('daily_ohlcv')
ds = t.to_lance()

# Check stock code formats
scanner = ds.scanner(columns=['stock_code'], filter="stock_code LIKE '%000001%'")
table = scanner.to_table()
df = pl.from_arrow(table)
print("Stock codes matching '000001':")
print(df['stock_code'].unique().to_list())

# Check date range for 000001
scanner2 = ds.scanner(columns=['stock_code', 'trade_date'], filter="stock_code LIKE '%000001%'")
table2 = scanner2.to_table()
df2 = pl.from_arrow(table2).sort('trade_date')
print(f"\nDate range for 000001*: {len(df2)} rows")
if not df2.is_empty():
    print(f"  Earliest: {df2['trade_date'].min()}")
    print(f"  Latest: {df2['trade_date'].max()}")
    print(f"  Sample codes: {df2['stock_code'].unique().to_list()[:5]}")

# Check a sample of stock codes
scanner3 = ds.scanner(columns=['stock_code'])
table3 = scanner3.to_table()
df3 = pl.from_arrow(table3)
codes = df3['stock_code'].unique().to_list()
print(f"\nTotal unique codes: {len(codes)}")
print(f"Sample codes: {sorted(codes)[:10]}")

# Check if there's a different format
has_suffix = sum(1 for c in codes if '.' in c)
no_suffix = sum(1 for c in codes if '.' not in c)
print(f"Codes with suffix (.SZ/.SH): {has_suffix}")
print(f"Codes without suffix: {no_suffix}")
