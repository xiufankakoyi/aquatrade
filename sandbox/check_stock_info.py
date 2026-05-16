"""检查 stock_info.parquet 中的 stock_code 格式"""
import polars as pl

# 读取 stock_info
info_path = 'data/parquet_data/stock_info.parquet'
info_df = pl.read_parquet(info_path)

print(f'stock_info 行数: {len(info_df)}')
print(f'列名: {info_df.columns}')
print()

# 检查 stock_code 格式
codes = info_df['stock_code'].unique().to_list()
print(f'唯一股票数: {len(codes)}')
print(f'stock_code 示例: {codes[:30]}')
print()

# 统计各板块
sz_count = sum(1 for c in codes if str(c).startswith('0'))
cyb_count = sum(1 for c in codes if str(c).startswith('3'))
sh_count = sum(1 for c in codes if str(c).startswith('6'))
kcb_count = sum(1 for c in codes if str(c).startswith('688'))

print(f'沪市主板(6开头): {sh_count}')
print(f'科创板(688): {kcb_count}')
print(f'深市主板(0开头): {sz_count}')
print(f'创业板(3开头): {cyb_count}')
print()

# 检查聚宽买入的股票
print('检查聚宽买入的股票:')
target_stocks = ['000030', '002626', '002403']
for code in target_stocks:
    found = code in codes
    print(f'  {code}: {"存在" if found else "不存在"}')
