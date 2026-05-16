"""
模拟 PositionManager 的完整更新流程
"""
from core.portfolio.position_manager import PositionManager, Position
import pandas as pd

manager = PositionManager()

# 获取 DataFrame
df = manager._get_positions_df()
print("读取后的 DataFrame:")
print(f"is_active dtype: {df['is_active'].dtype}")
print(f"is_active values: {df['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 模拟更新
mask = df['id'] == df['id'].iloc[0]
print(f"\nmask: {mask.tolist()}")

# 赋值
df.loc[mask, 'is_active'] = 1 if True else 0
print("\n赋值后:")
print(f"is_active dtype: {df['is_active'].dtype}")
print(f"is_active values: {df['is_active'].tolist()}")
print(f"is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 尝试保存
print("\n尝试保存...")
try:
    manager._save_positions_df(df)
    print("保存成功!")
except Exception as e:
    print(f"保存失败: {e}")
