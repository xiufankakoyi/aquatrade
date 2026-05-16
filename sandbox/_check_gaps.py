import sys
sys.path.insert(0, '.')
import lancedb
import polars as pl

db = lancedb.connect('data/lancedb')
t = db.open_table('daily_ohlcv')
ds = t.to_lance()

# Check date range for codes WITHOUT suffix
scanner = ds.scanner(
    columns=['stock_code', 'trade_date'],
    filter="stock_code = '000001'"
)
table = scanner.to_table()
df = pl.from_arrow(table).sort('trade_date')
print(f"000001 (no suffix): {len(df)} rows")
if not df.is_empty():
    print(f"  Date range: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

# Check date range for codes WITH suffix
scanner2 = ds.scanner(
    columns=['stock_code', 'trade_date'],
    filter="stock_code = '000001.SZ'"
)
table2 = scanner2.to_table()
df2 = pl.from_arrow(table2).sort('trade_date')
print(f"\n000001.SZ (with suffix): {len(df2)} rows")
if not df2.is_empty():
    print(f"  Date range: {df2['trade_date'].min()} ~ {df2['trade_date'].max()}")

# Count total rows by format
scanner3 = ds.scanner(columns=['stock_code'])
table3 = scanner3.to_table()
df3 = pl.from_arrow(table3)
codes = df3['stock_code'].to_list()
with_suffix = sum(1 for c in codes if '.' in str(c))
without_suffix = sum(1 for c in codes if '.' not in str(c))
print(f"\nTotal rows: with_suffix={with_suffix}, without_suffix={without_suffix}")

# Check overall date range
scanner4 = ds.scanner(columns=['trade_date'])
table4 = scanner4.to_table()
df4 = pl.from_arrow(table4)
dates = df4['trade_date'].to_list()
print(f"\nOverall date range: {min(dates)} ~ {max(dates)}")
