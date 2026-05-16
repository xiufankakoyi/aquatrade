"""
直接测试 PositionManager 删除
"""
import sys
sys.path.insert(0, '.')

from core.portfolio.position_manager import PositionManager

pm = PositionManager()

print("=== 获取持仓 ===")
df = pm._get_positions_df()
print(f"持仓数量: {len(df)}")

if len(df) > 0:
    target_id = int(df.iloc[0]['id'])
    print(f"\n=== 删除 ID={target_id} ===")
    try:
        success = pm.delete_position(target_id)
        print(f"删除结果: {success}")
    except Exception as e:
        print(f"删除失败: {e}")
        import traceback
        traceback.print_exc()
