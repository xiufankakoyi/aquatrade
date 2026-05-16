"""
模拟前端请求，检查是否能删除
"""
import requests

BASE_URL = 'http://localhost:5000'

# 1. 获取当前持仓
print("=== 1. 获取当前持仓 ===")
resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
data = resp.json()
print(f"成功: {data.get('success')}")
positions = data.get('data', [])
print(f"持仓数量: {len(positions)}")
for p in positions:
    print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")

if positions:
    # 找平安银行
    pingan = [p for p in positions if '平安银行' in p.get('stock_name', '')]
    if pingan:
        target = pingan[0]
        print(f"\n=== 2. 删除平安银行 ID={target['id']} ===")
        
        # 模拟前端请求
        del_resp = requests.delete(f"{BASE_URL}/api/portfolio/positions/{target['id']}")
        print(f"状态码: {del_resp.status_code}")
        print(f"响应: {del_resp.json()}")
        
        # 验证
        print("\n=== 3. 验证删除结果 ===")
        resp2 = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
        positions2 = resp2.json().get('data', [])
        pingan2 = [p for p in positions2 if '平安银行' in p.get('stock_name', '')]
        print(f"剩余平安银行持仓: {len(pingan2)}")
    else:
        print("没有找到平安银行持仓")
