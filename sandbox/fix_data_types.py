"""
检查 ArcticDB 写入和读取的数据类型
"""
import pandas as pd
from arcticdb import Arctic

arctic = Arctic("lmdb://./data/arctic_db")
lib = arctic['portfolio']

# 读取当前数据
df = lib.read('positions').data
print("ArcticDB 读取的数据:")
print(f"dtypes:\n{df.dtypes}")
print()
print(f"is_active dtype: {df['is_active'].dtype}")
print(f"is_active values: {df['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 创建一个完全新的 DataFrame，确保类型正确
print("\n创建新的 DataFrame...")
new_df = pd.DataFrame({
    'id': df['id'].tolist(),
    'stock_code': df['stock_code'].tolist(),
    'stock_name': df['stock_name'].tolist(),
    'buy_price': df['buy_price'].tolist(),
    'shares': df['shares'].tolist(),
    'cost': df['cost'].tolist(),
    'buy_date': df['buy_date'].tolist(),
    'stop_loss': df['stop_loss'].tolist(),
    'take_profit': df['take_profit'].tolist(),
    'notes': df['notes'].tolist(),
    'is_active': [int(x) for x in df['is_active'].tolist()],  # 强制 int
    'created_at': df['created_at'].tolist(),
    'updated_at': df['updated_at'].tolist()
})

print(f"新 DataFrame is_active dtype: {new_df['is_active'].dtype}")
print(f"新 DataFrame is_active values: {new_df['is_active'].tolist()}")

# 写入
print("\n写入 ArcticDB...")
try:
    lib.write('positions', new_df)
    print("写入成功!")
except Exception as e:
    print(f"写入失败: {e}")
    import traceback
    traceback.print_exc()

# 再读取
print("\n再次读取:")
df2 = lib.read('positions').data
print(f"is_active dtype: {df2['is_active'].dtype}")
print(f"is_active values: {df2['is_active'].tolist()}")
