"""
导入历史交易记录到持仓历史
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

from core.portfolio.position_history_manager import PositionHistoryManager, PositionHistory
from core.portfolio.position_manager import PositionManager, Position
from datetime import datetime

# 交易记录数据 (股票代码, 操作, 价格, 数量, 日期, 股票名称)
trades = [
    # 2025-02-12 买入
    ('000066', 'buy', 16.56, 3000, '2025-02-12', '中国长城'),
    ('600941', 'buy', 93.69, 300, '2025-02-12', '中国移动'),
    ('600755', 'buy', 6.62, 5000, '2025-02-12', '厦门国贸'),
    ('600660', 'buy', 60.15, 1000, '2025-02-12', '福耀玻璃'),
    # 2025-02-13 卖出
    ('600660', 'sell', 59.76, 1000, '2025-02-13', '福耀玻璃'),
    ('600755', 'sell', 6.63, 5000, '2025-02-13', '厦门国贸'),
    # 2025-02-13 买入
    ('603256', 'buy', 75.00, 700, '2025-02-13', '宏和科技'),
    ('164906', 'buy', 1.372, 72800, '2025-02-13', '中概互联'),
    # 2025-02-13 卖出 (中国长城卖出1200股，剩余1800股)
    ('000066', 'reduce', 16.80, 1200, '2025-02-13', '中国长城'),
]

def main():
    history_manager = PositionHistoryManager()
    position_manager = PositionManager()
    
    # 获取现有持仓
    existing_positions = {p.stock_code: p for p in position_manager.get_all_positions(active_only=True)}
    
    print("开始导入交易记录...")
    
    for code, action, price, shares, date, name in trades:
        try:
            # 计算金额
            amount = price * shares
            
            # 查找或创建持仓
            position = existing_positions.get(code)
            position_id = None
            
            if action == 'buy':
                # 新建持仓
                if position:
                    print(f"  警告: {code} {name} 已有持仓，跳过买入")
                    continue
                
                new_position = Position(
                    stock_code=code,
                    stock_name=name,
                    buy_price=price,
                    shares=shares,
                    cost=amount,
                    buy_date=date,
                    notes='',
                    is_active=True
                )
                new_id = position_manager.add_position(new_position)
                new_position.id = new_id
                position_id = new_id
                existing_positions[code] = new_position
                print(f"  创建持仓: {code} {name} {shares}股 @ {price}")
                
            elif action == 'sell':
                # 清仓
                if not position:
                    print(f"  警告: {code} {name} 没有持仓，跳过卖出")
                    continue
                
                position_id = position.id
                position_manager.delete_position(position.id)
                del existing_positions[code]
                print(f"  清仓: {code} {name} {shares}股 @ {price}")
                
            elif action == 'reduce':
                # 减仓
                if not position:
                    print(f"  警告: {code} {name} 没有持仓，跳减持")
                    continue
                
                if shares >= position.shares:
                    # 全部卖出，删除持仓
                    position_id = position.id
                    position_manager.delete_position(position.id)
                    del existing_positions[code]
                    action = 'sell'
                    print(f"  清仓: {code} {name} {shares}股 @ {price}")
                else:
                    # 部分卖出，更新持仓
                    position_id = position.id
                    avg_cost = position.cost / position.shares
                    cost_reduction = avg_cost * shares
                    new_shares = position.shares - shares
                    new_cost = position.cost - cost_reduction
                    
                    updated_position = Position(
                        id=position.id,
                        stock_code=code,
                        stock_name=name,
                        buy_price=position.buy_price,
                        shares=new_shares,
                        cost=new_cost,
                        buy_date=position.buy_date,
                        notes=position.notes,
                        is_active=True
                    )
                    position_manager.update_position(updated_position)
                    existing_positions[code] = position_manager.get_position(position.id)
                    print(f"  减仓: {code} {name} {shares}股 @ {price}, 剩余{new_shares}股")
            
            # 添加历史记录
            if position_id:
                history = PositionHistory(
                    id=None,
                    position_id=position_id,
                    stock_code=code,
                    stock_name=name,
                    action=action,
                    shares=shares,
                    price=price,
                    amount=amount if action in ['buy', 'add'] else -amount,
                    date=date,
                    notes=f'{action} {shares}股，价格{price}'
                )
                history_id = history_manager.add_history(history)
                print(f"    历史记录ID: {history_id}")
                
        except Exception as e:
            print(f"  错误: {code} {name} - {e}")
            import traceback
            traceback.print_exc()
    
    print("\n导入完成!")
    
    # 显示当前持仓
    print("\n当前持仓:")
    positions = position_manager.get_all_positions(active_only=True)
    for p in positions:
        print(f"  {p.stock_code} {p.stock_name}: {p.shares}股, 成本{p.cost:.2f}")

if __name__ == '__main__':
    main()
