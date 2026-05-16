import sys
sys.path.insert(0, '.')
import lancedb
import polars as pl

db = lancedb.connect('data/lancedb')

# Check factors table
t = db.open_table('factors')
ds = t.to_lance()
scanner = ds.scanner(columns=['stock_code'])
table = scanner.to_table()
df = pl.from_arrow(table)
codes = df['stock_code'].to_list()
with_suffix = sum(1 for c in codes if '.' in str(c))
without_suffix = sum(1 for c in codes if '.' not in str(c))
print(f"factors: with_suffix={with_suffix}, without_suffix={without_suffix}")

# Check index_daily
t2 = db.open_table('index_daily')
ds2 = t2.to_lance()
scanner2 = ds2.scanner(columns=['symbol'])
table2 = scanner2.to_table()
df2 = pl.from_arrow(table2)
symbols = df2['symbol'].to_list()
print(f"index_daily symbols: {set(symbols)}")

# Check sector_daily
t3 = db.open_table('sector_daily')
ds3 = t3.to_lance()
scanner3 = ds3.scanner(columns=['sector_code'])
table3 = scanner3.to_table()
df3 = pl.from_arrow(table3)
codes3 = df3['sector_code'].to_list()
with_suffix3 = sum(1 for c in codes3 if '.' in str(c))
without_suffix3 = sum(1 for c in codes3 if '.' not in str(c))
print(f"sector_daily: with_suffix={with_suffix3}, without_suffix={without_suffix3}")
