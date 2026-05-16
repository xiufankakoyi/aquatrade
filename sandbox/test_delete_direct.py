import sys
sys.path.insert(0, '.')

from core.portfolio.position_manager import PositionManager

pm = PositionManager()

print("=== 删除前 ===")
df = pm._get_positions_df()
print(f"持仓数量: {len(df)}")
print(df.dtypes)

if len(df) > 0:
    first_id = df.iloc[0]['id']
    print(f"\n=== 尝试删除 ID={first_id} ===")
    success = pm.delete_position(int(first_id))
    print(f"删除结果: {success}")
    
    print("\n=== 删除后 ===")
    df2 = pm._get_positions_df()
    print(f"持仓数量: {len(df2)}")
