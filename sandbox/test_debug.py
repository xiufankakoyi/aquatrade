#!/usr/bin/env python3
"""
调试脚本 - 检查后端 API 和股票信息
"""
import requests
import json

BASE_URL = "http://localhost:5001"

def test_api():
    """测试 API"""
    print("=" * 80)
    print("测试后端 API")
    print("=" * 80)
    
    # 1. 测试策略列表
    print("\n[1/4] 获取策略列表...")
    try:
        r = requests.get(f"{BASE_URL}/api/strategies", timeout=10)
        print(f"  状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            strategies = data.get('strategies', [])
            print(f"  找到 {len(strategies)} 个策略")
            for s in strategies[:3]:
                print(f"    - {s.get('name')}: {s.get('description', 'N/A')[:50]}...")
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    
    # 2. 测试股票信息
    print("\n[2/4] 获取股票信息...")
    try:
        # 测试几个股票代码
        test_codes = ["600121", "000001", "600000"]
        r = requests.get(f"{BASE_URL}/api/latest_price?symbols={','.join(test_codes)}", timeout=10)
        print(f"  状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    
    # 3. 测试回测接口
    print("\n[3/4] 测试回测接口...")
    try:
        r = requests.post(f"{BASE_URL}/api/backtest", json={
            "strategy": "simple_volume_v3",
            "startDate": "2024-01-01",
            "endDate": "2024-03-01"
        }, timeout=10)
        print(f"  状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
        else:
            print(f"  错误响应: {r.text[:500]}")
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    
    # 4. 测试 ArcticDB 状态
    print("\n[4/4] 检查 ArcticDB 状态...")
    try:
        r = requests.get(f"{BASE_URL}/api/db/status", timeout=10)
        print(f"  状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_api()
