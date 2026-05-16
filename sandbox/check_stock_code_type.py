"""检查 stock_code 的数据类型和值"""
import polars as pl

# 读取 Parquet 文件
df = pl.read_parquet('data/parquet_data/stock_daily.parquet')

print(f'总行数: {len(df)}')
print(f'Schema:')
for name, dtype in df.schema.items():
    print(f'  {name}: {dtype}')
print()

# 获取 stock_code 的唯一值
stock_codes = df['stock_code'].unique().to_list()
print(f'唯一 stock_code 数: {len(stock_codes)}')

# 检查 stock_code 的长度
lengths = [len(str(c)) for c in stock_codes]
from collections import Counter
length_counts = Counter(lengths)
print(f'stock_code 长度分布:')
for length, count in sorted(length_counts.items()):
    print(f'  长度 {length}: {count} 个')
print()

# 显示一些长度为 1-5 的 stock_code
short_codes = [c for c in stock_codes if len(str(c)) < 6]
print(f'长度小于6的 stock_code 示例 ({len(short_codes)} 个):')
print(short_codes[:30])
print()

# 显示一些长度为 6 的 stock_code
long_codes = [c for c in stock_codes if len(str(c)) == 6]
print(f'长度为6的 stock_code 示例 ({len(long_codes)} 个):')
print(long_codes[:30])
