"""
在服务进程中检查数据
"""
import sys
sys.path.insert(0, '.')

from core.portfolio.position_manager import PositionManager

manager = PositionManager()

# 获取 DataFrame
df = manager._get_positions_df()
print("服务进程中的 DataFrame:")
print(f"dtypes:\n{df.dtypes}")
print()
print(f"is_active dtype: {df['is_active'].dtype}")
print(f"is_active values: {df['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 检查 ArcticDB 原始数据
from arcticdb import Arctic
arctic = Arctic("lmdb://./data/arctic_db")
lib = arctic['portfolio']
df_arctic = lib.read('positions').data
print("\nArcticDB 原始数据:")
print(f"dtypes:\n{df_arctic.dtypes}")
print()
print(f"is_active dtype: {df_arctic['is_active'].dtype}")
print(f"is_active values: {df_arctic['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df_arctic['is_active'].tolist()]}")

# 检查 Parquet
import pandas as pd
df_parquet = pd.read_parquet('data/parquet_data/portfolio_positions.parquet')
print("\nParquet 数据:")
print(f"dtypes:\n{df_parquet.dtypes}")
print()
print(f"is_active dtype: {df_parquet['is_active'].dtype}")
print(f"is_active values: {df_parquet['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df_parquet['is_active'].tolist()]}")
