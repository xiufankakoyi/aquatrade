"""直接检查 Parquet 文件中的数据"""
import polars as pl
import os

# 直接从 Parquet 文件读取
parquet_path = 'data/parquet_data/stock_daily.parquet'

df = pl.read_parquet(parquet_path)
print(f'Parquet 文件总行数: {len(df)}')
print(f'列: {df.columns}')
print()

# 过滤 2025-01-02 的数据
df_0102 = df.filter(pl.col('trade_date') == '2025-01-02')
print(f'2025-01-02 的股票数: {len(df_0102)}')

codes = df_0102['stock_code'].unique().to_list()
print(f'唯一股票数: {len(codes)}')
print()

# 统计各板块
sz_count = sum(1 for c in codes if str(c).startswith('0'))
cyb_count = sum(1 for c in codes if str(c).startswith('3'))
sh_count = sum(1 for c in codes if str(c).startswith('6'))
kcb_count = sum(1 for c in codes if str(c).startswith('688'))
bj_count = sum(1 for c in codes if str(c).startswith(('8', '9', '4', '43', '83', '87')))

print(f'沪市主板(6开头): {sh_count}')
print(f'科创板(688): {kcb_count}')
print(f'深市主板(0开头): {sz_count}')
print(f'创业板(3开头): {cyb_count}')
print(f'北交所(8/9/4开头): {bj_count}')
print()

# 检查聚宽买入的股票
print('检查聚宽买入的股票:')
target_stocks = ['000030', '002626', '002403']
for code in target_stocks:
    found = code in codes
    print(f'  {code}: {"存在" if found else "不存在"}')

# 检查是否有 000 开头的股票
print()
print('000 开头的股票示例:')
zero_codes = [c for c in codes if str(c).startswith('0')]
print(zero_codes[:20])
