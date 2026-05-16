import sys
sys.path.insert(0, '.')
import lancedb
import polars as pl

db = lancedb.connect('data/lancedb')
t = db.open_table('daily_ohlcv')
ds = t.to_lance()

# Find codes without suffix
scanner = ds.scanner(columns=['stock_code'])
table = scanner.to_table()
df = pl.from_arrow(table)

# Filter codes without suffix
no_suffix_codes = df.filter(
    ~df['stock_code'].str.contains(r'\.')
)['stock_code'].unique().sort().to_list()

print(f"Codes without suffix: {len(no_suffix_codes)}")
print(f"Sample: {no_suffix_codes[:30]}")

# Check code lengths
from collections import Counter
length_dist = Counter(len(str(c)) for c in no_suffix_codes)
print(f"\nCode length distribution: {dict(sorted(length_dist.items()))}")

# Check what 5-char codes look like
codes_5 = [c for c in no_suffix_codes if len(str(c)) == 5]
print(f"\n5-char codes sample: {codes_5[:20]}")

codes_4 = [c for c in no_suffix_codes if len(str(c)) == 4]
print(f"4-char codes sample: {codes_4[:20]}")

codes_6 = [c for c in no_suffix_codes if len(str(c)) == 6]
print(f"6-char codes sample: {codes_6[:20]}")
