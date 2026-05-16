"""
详细测试失败的接口
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000/api/portfolio"

def test_push():
    """测试推送飞书接口"""
    print("=" * 60)
    print("测试 POST /push")
    print("=" * 60)
    
    url = f"{BASE_URL}/push"
    
    # 测试不带参数
    print("\n1. 不带 webhook_url:")
    try:
        response = requests.post(url, json={}, timeout=10)
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:500]}")
    except Exception as e:
        print(f"   异常: {e}")
    
    # 测试带无效 webhook_url
    print("\n2. 带无效 webhook_url:")
    try:
        response = requests.post(url, json={"webhook_url": "https://invalid-webhook.com"}, timeout=10)
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:500]}")
    except Exception as e:
        print(f"   异常: {e}")

def test_update_position():
    """测试更新持仓接口"""
    print("\n" + "=" * 60)
    print("测试 PUT /positions/{id}")
    print("=" * 60)
    
    # 先获取一个持仓
    print("\n1. 获取现有持仓:")
    try:
        response = requests.get(f"{BASE_URL}/positions", params={"active_only": "true"}, timeout=10)
        data = response.json()
        if data.get("success") and data.get("data"):
            positions = data["data"]
            if positions:
                pos = positions[0]
                print(f"   找到持仓: ID={pos['id']}, {pos['stock_name']}")
                
                # 尝试更新
                print("\n2. 尝试更新:")
                update_data = {
                    "stock_code": pos['stock_code'],
                    "stock_name": pos['stock_name'],
                    "buy_price": pos['buy_price'],
                    "shares": pos['shares'],
                    "cost": pos['cost'],
                    "buy_date": pos['buy_date'],
                    "is_active": True
                }
                print(f"   请求数据: {json.dumps(update_data, ensure_ascii=False)}")
                
                response = requests.put(
                    f"{BASE_URL}/positions/{pos['id']}", 
                    json=update_data, 
                    timeout=10
                )
                print(f"   状态码: {response.status_code}")
                print(f"   响应: {response.text[:1000]}")
            else:
                print("   没有找到持仓")
        else:
            print(f"   获取失败: {data}")
    except Exception as e:
        print(f"   异常: {e}")

if __name__ == "__main__":
    test_push()
    test_update_position()
