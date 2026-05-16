"""
调试 Polars DataFrame 中重复列的行为
"""
import polars as pl

# 创建一个 DataFrame
df = pl.DataFrame({
    'a': [1, 2, 3],
    'b': [4, 5, 6]
})

print("原始 DataFrame:")
print(df)

# 添加一个重复的列
df2 = df.with_columns([
    pl.col('a').alias('a')
])

print("\n添加重复列后的 DataFrame:")
print(df2)
print(f"列: {df2.columns}")

# 检查 'a' 列的值
print(f"\n'a' 列的值: {df2['a'].to_list()}")
