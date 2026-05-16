import sys
sys.path.insert(0, '.')
import lancedb
import polars as pl

db = lancedb.connect('data/lancedb')
t = db.open_table('daily_ohlcv')
ds = t.to_lance()

# Verify 000001.SZ now has full data
scanner = ds.scanner(
    columns=['stock_code', 'trade_date'],
    filter="stock_code = '000001.SZ'"
)
table = scanner.to_table()
df = pl.from_arrow(table).sort('trade_date')
print(f"000001.SZ: {len(df)} rows")
print(f"Date range: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

# Check no codes without suffix remain
scanner2 = ds.scanner(columns=['stock_code'])
table2 = scanner2.to_table()
df2 = pl.from_arrow(table2)
codes = df2['stock_code'].to_list()
no_suffix = sum(1 for c in codes if '.' not in str(c) and len(str(c)) >= 6)
with_suffix = sum(1 for c in codes if '.' in str(c))
print(f"\nTotal: with_suffix={with_suffix:,}, without_suffix={no_suffix:,}")

# Verify factors too
t2 = db.open_table('factors')
ds2 = t2.to_lance()
scanner3 = ds2.scanner(columns=['stock_code'])
table3 = scanner3.to_table()
df3 = pl.from_arrow(table3)
codes3 = df3['stock_code'].to_list()
no_suffix3 = sum(1 for c in codes3 if '.' not in str(c) and len(str(c)) >= 6)
with_suffix3 = sum(1 for c in codes3 if '.' in str(c))
print(f"factors: with_suffix={with_suffix3:,}, without_suffix={no_suffix3:,}")
