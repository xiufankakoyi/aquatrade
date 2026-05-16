"""
调试 Polars DataFrame 中 select 方法对重复列的处理
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
    (pl.col('a') * 10).alias('a')
])

print("\n添加重复列后的 DataFrame:")
print(df2)
print(f"列: {df2.columns}")

# 使用 select 方法选择列
df3 = df2.select(['a', 'b'])

print("\n使用 select 方法选择列:")
print(df3)
print(f"'a' 列的值: {df3['a'].to_list()}")
