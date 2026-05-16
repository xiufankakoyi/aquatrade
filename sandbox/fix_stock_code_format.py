"""
修复 stock_daily.parquet 中的 stock_code 格式

问题：stock_code 列的前导零丢失，例如 000036 变成了 36
解决：将所有 stock_code 统一格式化为 6 位数字
"""
import polars as pl
import os

# 文件路径
parquet_path = 'data/parquet_data/stock_daily.parquet'
backup_path = 'data/parquet_data/stock_daily_backup.parquet'

print("=" * 60)
print("修复 stock_code 格式")
print("=" * 60)

# 1. 备份原文件
print("\n[1] 备份原文件...")
if os.path.exists(parquet_path):
    df = pl.read_parquet(parquet_path)
    df.write_parquet(backup_path)
    print(f"   已备份到: {backup_path}")
else:
    print(f"   文件不存在: {parquet_path}")
    exit(1)

# 2. 检查当前 stock_code 格式
print("\n[2] 检查当前 stock_code 格式...")
stock_codes = df['stock_code'].unique().to_list()
print(f"   唯一股票数: {len(stock_codes)}")

# 统计长度分布
from collections import Counter
lengths = [len(str(c)) for c in stock_codes]
length_counts = Counter(lengths)
print(f"   stock_code 长度分布:")
for length, count in sorted(length_counts.items()):
    print(f"     长度 {length}: {count} 个")

# 显示一些长度不正确的示例
short_codes = [c for c in stock_codes if len(str(c)) < 6]
print(f"\n   长度小于6的 stock_code 示例: {short_codes[:10]}")

# 3. 修复 stock_code 格式
print("\n[3] 修复 stock_code 格式...")

# 使用 ts_code 重新提取 stock_code，确保格式正确
df_fixed = df.with_columns([
    pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
])

# 验证修复结果
fixed_codes = df_fixed['stock_code'].unique().to_list()
fixed_lengths = [len(str(c)) for c in fixed_codes]
fixed_length_counts = Counter(fixed_lengths)
print(f"   修复后 stock_code 长度分布:")
for length, count in sorted(fixed_length_counts.items()):
    print(f"     长度 {length}: {count} 个")

# 4. 保存修复后的文件
print("\n[4] 保存修复后的文件...")
df_fixed.write_parquet(parquet_path)
print(f"   已保存到: {parquet_path}")

# 5. 验证修复结果
print("\n[5] 验证修复结果...")
df_verify = pl.read_parquet(parquet_path)
verify_codes = df_verify['stock_code'].unique().to_list()

# 检查聚宽买入的股票
target_stocks = ['000030', '002626', '002403']
print(f"\n   检查聚宽买入的股票:")
for code in target_stocks:
    found = code in verify_codes
    print(f"     {code}: {'存在' if found else '不存在'}")

print("\n" + "=" * 60)
print("修复完成!")
print("=" * 60)
