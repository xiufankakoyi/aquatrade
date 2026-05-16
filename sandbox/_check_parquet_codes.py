import sys
sys.path.insert(0, '.')
import zipfile
import polars as pl
import io

z = zipfile.ZipFile('data/parquet_data.zip')

# Check stock_daily.parquet
name = 'stock_daily.parquet'
data = z.read(name)
df = pl.read_parquet(io.BytesIO(data))

codes = df['stock_code'].unique().to_list()
has_suffix = sum(1 for c in codes if '.' in str(c))
no_suffix = sum(1 for c in codes if '.' not in str(c))
print(f"stock_daily.parquet:")
print(f"  Total unique codes: {len(codes)}")
print(f"  With suffix (.SZ/.SH): {has_suffix}")
print(f"  Without suffix: {no_suffix}")
print(f"  Sample: {sorted([str(c) for c in codes])[:10]}")

# Check base_daily_archive
name2 = 'base_daily_archive.parquet'
data2 = z.read(name2)
df2 = pl.read_parquet(io.BytesIO(data2))
codes2 = df2['stock_code'].unique().to_list()
has_suffix2 = sum(1 for c in codes2 if '.' in str(c))
no_suffix2 = sum(1 for c in codes2 if '.' not in str(c))
print(f"\nbase_daily_archive.parquet:")
print(f"  With suffix: {has_suffix2}, Without: {no_suffix2}")
print(f"  Sample: {sorted([str(c) for c in codes2])[:10]}")

# Check base_daily_hot
name3 = 'base_daily_hot.parquet'
data3 = z.read(name3)
df3 = pl.read_parquet(io.BytesIO(data3))
codes3 = df3['stock_code'].unique().to_list()
has_suffix3 = sum(1 for c in codes3 if '.' in str(c))
no_suffix3 = sum(1 for c in codes3 if '.' not in str(c))
print(f"\nbase_daily_hot.parquet:")
print(f"  With suffix: {has_suffix3}, Without: {no_suffix3}")
print(f"  Sample: {sorted([str(c) for c in codes3])[:10]}")
