"""检查 Parquet 文件的 schema"""
import polars as pl

# 读取 Parquet 文件
df = pl.read_parquet('data/parquet_data/stock_daily.parquet')

print('Schema:')
print(df.schema)
print()

print('stock_code 列类型:', df['stock_code'].dtype)
print('ts_code 列类型:', df['ts_code'].dtype)
print()

# 检查 stock_code 为 36 的数据
result = df.filter(pl.col('stock_code') == '36')
print(f'stock_code = 36 的数据: {len(result)} 条')
print(result.select(['stock_code', 'ts_code']).head(10).to_pandas().to_string())
