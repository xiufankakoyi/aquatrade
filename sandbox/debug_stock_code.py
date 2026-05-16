"""调试 stock_code 列"""
import polars as pl

# 读取 stock_daily
df = pl.read_parquet('data/parquet_data/stock_daily.parquet')
df = df.filter(pl.col('trade_date') == '2025-01-02')

print(f'总行数: {len(df)}')
print()

# 检查 stock_code 和 ts_code 的对应关系
print('stock_code 和 ts_code 对应关系:')
print(df.select(['stock_code', 'ts_code']).head(30).to_pandas().to_string())
print()

# 查找 000036
print('查找 000036:')
result = df.filter(pl.col('ts_code').str.contains('000036'))
print(f'  ts_code 包含 000036: {len(result)} 条')
if len(result) > 0:
    print(result.select(['stock_code', 'ts_code']).to_pandas().to_string())

result2 = df.filter(pl.col('stock_code') == '000036')
print(f'  stock_code = 000036: {len(result2)} 条')
print()

# 统计 stock_code 各板块
stock_codes = df['stock_code'].unique().to_list()
sz_count = sum(1 for c in stock_codes if str(c).startswith('0'))
print(f'stock_code 深市主板(0开头): {sz_count}')

# 统计 ts_code 各板块
ts_codes = df['ts_code'].unique().to_list()
sz_count2 = sum(1 for c in ts_codes if '.SZ' in str(c) and str(c).startswith('0'))
print(f'ts_code 深市主板(0开头.SZ): {sz_count2}')
