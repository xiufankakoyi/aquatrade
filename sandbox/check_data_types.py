"""
检查当前数据类型
"""
import sys
sys.path.insert(0, '.')

from core.portfolio.position_manager import PositionManager

pm = PositionManager()
df = pm._get_positions_df()

print("=== 数据内容 ===")
print(df)
print("\n=== 列类型 ===")
for col in df.columns:
    print(f"  {col}: {df[col].dtype} -> {type(df[col].iloc[0]) if len(df) > 0 else 'empty'}")
