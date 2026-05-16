"""
检查数据类型问题
"""
import pandas as pd
import os

# 检查 Parquet 文件
parquet_path = "data/parquet_data/portfolio_positions.parquet"
if os.path.exists(parquet_path):
    df = pd.read_parquet(parquet_path)
    print("Parquet 数据:")
    print(df.dtypes)
    print()
    print("is_active 列:")
    print(f"  dtype: {df['is_active'].dtype}")
    print(f"  values: {df['is_active'].tolist()}")
    print(f"  types: {[type(v) for v in df['is_active'].tolist()]}")

# 检查 ArcticDB
from arcticdb import Arctic
arctic = Arctic("lmdb://./data/arctic_db")
if 'portfolio' in arctic.list_libraries():
    lib = arctic['portfolio']
    if 'positions' in lib.list_symbols():
        df2 = lib.read('positions').data
        print("\nArcticDB 数据:")
        print(df2.dtypes)
        print()
        print("is_active 列:")
        print(f"  dtype: {df2['is_active'].dtype}")
        print(f"  values: {df2['is_active'].tolist()}")
        print(f"  types: {[type(v) for v in df2['is_active'].tolist()]}")
