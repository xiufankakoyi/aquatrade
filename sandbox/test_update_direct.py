"""
直接测试 PositionManager 的 update_position
"""
from core.portfolio.position_manager import PositionManager, Position

manager = PositionManager()

# 获取一个持仓
positions = manager.get_all_positions(active_only=True)
if positions:
    pos = positions[0]
    print(f"更新持仓: ID={pos.id}, {pos.stock_name}")
    print(f"原始 is_active: {pos.is_active}, type: {type(pos.is_active)}")
    
    # 创建更新后的 Position
    updated_pos = Position(
        id=pos.id,
        stock_code=pos.stock_code,
        stock_name=pos.stock_name,
        buy_price=pos.buy_price,
        shares=pos.shares,
        cost=pos.cost,
        buy_date=pos.buy_date,
        stop_loss=pos.stop_loss,
        take_profit=pos.take_profit,
        notes=pos.notes,
        is_active=True  # 这是 Python bool
    )
    
    print(f"更新 is_active: {updated_pos.is_active}, type: {type(updated_pos.is_active)}")
    
    # 调用 update
    try:
        success = manager.update_position(updated_pos)
        print(f"更新结果: {success}")
    except Exception as e:
        print(f"更新失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("没有持仓")
