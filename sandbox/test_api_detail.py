"""
模拟完整的 API 更新流程
"""
import requests
import json

BASE_URL = "http://localhost:5000/api/portfolio"

# 1. 获取持仓列表
print("1. 获取持仓列表...")
resp = requests.get(f"{BASE_URL}/positions", params={"active_only": "true"})
data = resp.json()
print(f"状态码: {resp.status_code}")

if data.get("success") and data.get("data"):
    positions = data["data"]
    pos = positions[0]
    print(f"找到持仓: ID={pos['id']}, {pos['stock_name']}")
    print(f"is_active: {pos['is_active']}, type: {type(pos['is_active'])}")
    
    # 2. 尝试更新
    print("\n2. 尝试更新...")
    update_data = {
        "stock_code": pos['stock_code'],
        "stock_name": pos['stock_name'],
        "buy_price": pos['buy_price'],
        "shares": pos['shares'],
        "cost": pos['cost'],
        "buy_date": pos['buy_date'],
        "is_active": True  # Python bool
    }
    
    print(f"请求数据: {json.dumps(update_data, ensure_ascii=False, indent=2)}")
    
    resp2 = requests.put(f"{BASE_URL}/positions/{pos['id']}", json=update_data)
    print(f"状态码: {resp2.status_code}")
    print(f"响应: {resp2.text}")
else:
    print(f"获取失败: {data}")
