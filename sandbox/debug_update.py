"""
详细调试 update_position 问题
"""
import pandas as pd
import numpy as np

# 模拟问题场景
df = pd.DataFrame({
    'id': [1, 2, 3],
    'stock_code': ['000001', '000002', '000003'],
    'is_active': [1, 1, 1]  # 初始是 int
})

print("初始 DataFrame:")
print(df)
print(f"is_active dtype: {df['is_active'].dtype}")

# 模拟 df.loc 赋值
mask = df['id'] == 1
df.loc[mask, 'is_active'] = 1 if True else 0  # Python int

print("\n使用 df.loc 赋值后:")
print(df)
print(f"is_active dtype: {df['is_active'].dtype}")
print(f"is_active values: {df['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 尝试 astype(int)
df['is_active'] = df['is_active'].astype(int)
print("\n使用 astype(int) 后:")
print(f"is_active dtype: {df['is_active'].dtype}")

# 模拟 bool 值赋值
df2 = pd.DataFrame({
    'id': [1, 2, 3],
    'stock_code': ['000001', '000002', '000003'],
    'is_active': [1, 1, 1]
})

mask2 = df2['id'] == 1
df2.loc[mask2, 'is_active'] = True  # bool 值

print("\n\n使用 bool 值赋值后:")
print(df2)
print(f"is_active dtype: {df2['is_active'].dtype}")
print(f"is_active values: {df2['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df2['is_active'].tolist()]}")

# 这是问题所在！当列是 int 类型时，赋值 bool 会导致混合类型
