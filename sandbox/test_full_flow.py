"""
完整模拟 PositionManager 的更新流程
"""
from core.portfolio.position_manager import PositionManager, Position
import pandas as pd

print("=== 完整模拟更新流程 ===\n")

manager = PositionManager()

# 1. 获取 DataFrame
print("1. 获取 DataFrame:")
df = manager._get_positions_df()
print(f"   is_active dtype: {df['is_active'].dtype}")
print(f"   is_active values: {df['is_active'].tolist()}")
print(f"   is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 2. 获取持仓
print("\n2. 获取持仓:")
positions = manager.get_all_positions(active_only=True)
pos = positions[0]
print(f"   ID={pos.id}, {pos.stock_name}")
print(f"   is_active: {pos.is_active}, type: {type(pos.is_active)}")

# 3. 创建更新后的 Position
print("\n3. 创建更新后的 Position:")
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
    is_active=True
)
print(f"   is_active: {updated_pos.is_active}, type: {type(updated_pos.is_active)}")

# 4. 模拟 update_position 中的操作
print("\n4. 模拟 update_position 操作:")
mask = df['id'] == updated_pos.id
print(f"   mask: {mask.tolist()}")

# 赋值
df.loc[mask, 'stock_code'] = updated_pos.stock_code
df.loc[mask, 'stock_name'] = updated_pos.stock_name
df.loc[mask, 'buy_price'] = updated_pos.buy_price
df.loc[mask, 'shares'] = updated_pos.shares
df.loc[mask, 'cost'] = updated_pos.cost
df.loc[mask, 'buy_date'] = updated_pos.buy_date
df.loc[mask, 'stop_loss'] = updated_pos.stop_loss
df.loc[mask, 'take_profit'] = updated_pos.take_profit
df.loc[mask, 'notes'] = updated_pos.notes or ''
df.loc[mask, 'is_active'] = 1 if updated_pos.is_active else 0

print(f"   赋值后 is_active dtype: {df['is_active'].dtype}")
print(f"   赋值后 is_active values: {df['is_active'].tolist()}")
print(f"   赋值后 is_active types: {[type(v) for v in df['is_active'].tolist()]}")

# 5. 调用 _save_positions_df
print("\n5. 调用 _save_positions_df:")
try:
    manager._save_positions_df(df)
    print("   保存成功!")
except Exception as e:
    print(f"   保存失败: {e}")
    import traceback
    traceback.print_exc()
