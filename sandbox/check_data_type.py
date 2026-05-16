"""
检查现有数据的 is_active 列类型
"""
import pandas as pd
import os

parquet_path = "data/parquet_data/portfolio_positions.parquet"

if os.path.exists(parquet_path):
    df = pd.read_parquet(parquet_path)
    print("现有数据:")
    print(df)
    print(f"\nis_active 列类型: {df['is_active'].dtype}")
    print(f"is_active 值: {df['is_active'].tolist()}")
    print(f"is_active 值类型: {[type(v) for v in df['is_active'].tolist()]}")
    
    # 转换为 int
    df['is_active'] = df['is_active'].astype(int)
    print(f"\n转换后 is_active 列类型: {df['is_active'].dtype}")
    print(f"转换后 is_active 值: {df['is_active'].tolist()}")
    
    # 保存
    df.to_parquet(parquet_path, index=False)
    print("\n已保存转换后的数据")
else:
    print(f"文件不存在: {parquet_path}")
