"""
通过API导入历史交易记录
"""
import requests

BASE_URL = "http://localhost:5000/api"

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

def get_positions():
    """获取现有持仓"""
    resp = requests.get(f"{BASE_URL}/portfolio/positions")
    if resp.status_code == 200:
        data = resp.json()
        if data.get('success'):
            return {p['stock_code']: p for p in data.get('data', [])}
    return {}

def add_position(code, name, price, shares, date):
    """添加持仓"""
    data = {
        "stock_code": code,
        "stock_name": name,
        "buy_price": price,
        "shares": shares,
        "cost": price * shares,
        "buy_date": date,
        "notes": "",
        "is_active": True
    }
    resp = requests.post(f"{BASE_URL}/portfolio/positions", json=data)
    if resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            return result.get('data', {}).get('id')
    return None

def delete_position(position_id):
    """删除持仓"""
    resp = requests.delete(f"{BASE_URL}/portfolio/positions/{position_id}")
    return resp.status_code == 200

def update_position(position):
    """更新持仓"""
    resp = requests.put(f"{BASE_URL}/portfolio/positions/{position['id']}", json=position)
    return resp.status_code == 200

def add_history(position_id, code, name, action, price, shares, amount, date):
    """添加历史记录"""
    data = {
        "position_id": position_id,
        "stock_code": code,
        "stock_name": name,
        "action": action,
        "shares": shares,
        "price": price,
        "amount": amount if action in ['buy', 'add'] else -amount,
        "date": date,
        "notes": f"{action} {shares}股，价格{price}"
    }
    resp = requests.post(f"{BASE_URL}/portfolio/position-history", json=data)
    if resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            return result.get('data', {}).get('id')
    return None

def main():
    print("开始导入交易记录...")
    
    # 获取现有持仓
    positions = get_positions()
    print(f"现有持仓: {len(positions)} 个")
    
    for code, action, price, shares, date, name in trades:
        try:
            amount = price * shares
            position = positions.get(code)
            position_id = None
            
            if action == 'buy':
                if position:
                    print(f"  警告: {code} {name} 已有持仓，跳过买入")
                    continue
                
                position_id = add_position(code, name, price, shares, date)
                if position_id:
                    positions[code] = {
                        'id': position_id,
                        'stock_code': code,
                        'stock_name': name,
                        'buy_price': price,
                        'shares': shares,
                        'cost': amount,
                        'buy_date': date
                    }
                    print(f"  创建持仓: {code} {name} {shares}股 @ {price}")
                else:
                    print(f"  错误: 创建持仓失败 {code} {name}")
                    
            elif action == 'sell':
                if not position:
                    print(f"  警告: {code} {name} 没有持仓，跳过卖出")
                    continue
                
                position_id = position['id']
                if delete_position(position['id']):
                    del positions[code]
                    print(f"  清仓: {code} {name} {shares}股 @ {price}")
                else:
                    print(f"  错误: 清仓失败 {code} {name}")
                    
            elif action == 'reduce':
                if not position:
                    print(f"  警告: {code} {name} 没有持仓，跳减持")
                    continue
                
                position_id = position['id']
                if shares >= position['shares']:
                    # 全部卖出
                    if delete_position(position['id']):
                        del positions[code]
                        action = 'sell'
                        print(f"  清仓: {code} {name} {shares}股 @ {price}")
                    else:
                        print(f"  错误: 清仓失败 {code} {name}")
                else:
                    # 部分卖出
                    avg_cost = position['cost'] / position['shares']
                    cost_reduction = avg_cost * shares
                    new_shares = position['shares'] - shares
                    new_cost = position['cost'] - cost_reduction
                    
                    position['shares'] = new_shares
                    position['cost'] = new_cost
                    
                    if update_position(position):
                        positions[code] = position
                        print(f"  减仓: {code} {name} {shares}股 @ {price}, 剩余{new_shares}股")
                    else:
                        print(f"  错误: 更新持仓失败 {code} {name}")
            
            # 添加历史记录
            if position_id:
                history_id = add_history(position_id, code, name, action, price, shares, amount, date)
                if history_id:
                    print(f"    历史记录ID: {history_id}")
                else:
                    print(f"    错误: 添加历史记录失败")
                    
        except Exception as e:
            print(f"  错误: {code} {name} - {e}")
    
    print("\n导入完成!")
    
    # 显示当前持仓
    print("\n当前持仓:")
    positions = get_positions()
    for code, p in positions.items():
        print(f"  {p['stock_code']} {p['stock_name']}: {p['shares']}股, 成本{p['cost']:.2f}")

if __name__ == '__main__':
    main()
