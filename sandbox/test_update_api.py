"""
测试数据更新 API
"""
import requests
import json

# 测试更新请求
print("=" * 80)
print("测试数据更新 API")
print("=" * 80)

# 1. 直接测试后端 API
print("\n[1] 直接测试后端 API (localhost:5000)...")
try:
    resp = requests.post('http://localhost:5000/api/db/update', timeout=5)
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"   Error: {e}")

# 2. 测试前端代理 (localhost:5173)
print("\n[2] 测试前端代理 (localhost:5173)...")
try:
    resp = requests.post('http://localhost:5173/api/db/update', timeout=5)
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 80)
print("如果 [2] 返回 500 错误，说明前端代理配置有问题")
print("如果 [2] 返回 200，说明后端处理请求时出错了")
print("=" * 80)
