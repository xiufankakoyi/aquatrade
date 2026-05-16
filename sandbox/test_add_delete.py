"""
添加测试数据并测试删除
"""
import requests

BASE_URL = 'http://localhost:5000'

# 添加测试数据
print("=== 添加测试数据 ===")
resp = requests.post(f'{BASE_URL}/api/portfolio/positions', json={
    'stock_code': '000001',
    'stock_name': '测试股票',
    'buy_price': 10.0,
    'shares': 100,
    'cost': 1000,
    'buy_date': '2024-01-01',
    'stop_loss': 9.0,
    'take_profit': 11.0,
    'notes': '测试'
})
print(f"添加结果: {resp.json()}")

# 获取持仓
print("\n=== 获取持仓 ===")
resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
positions = resp.json().get('data', [])
print(f"持仓数量: {len(positions)}")

if positions:
    target_id = positions[0]['id']
    print(f"\n=== 删除 ID={target_id} ===")
    del_resp = requests.delete(f'{BASE_URL}/api/portfolio/positions/{target_id}')
    print(f"删除结果: {del_resp.json()}")
