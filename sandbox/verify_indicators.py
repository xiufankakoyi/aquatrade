import polars as pl

df = pl.read_parquet(r"d:\aquatrade\data\parquet_data\stock_daily_with_indicators.parquet")
print(f"总行数: {len(df):,}")
print(f"总列数: {len(df.columns)}")
print("所有列名:")
for col in df.columns:
    print(f"  - {col}")
