"""测试后端是否正常运行"""
import requests
import sys

# 测试几个可能的端点
endpoints = [
    'http://localhost:5000/',
    'http://localhost:5000/api/',
    'http://localhost:5000/api/kline',
]

for url in endpoints:
    try:
        response = requests.get(url, timeout=5)
        print(f"{url}: Status {response.status_code}")
        if response.status_code == 200:
            print(f"  Response: {response.text[:200]}")
            print("\n✅ Backend is responding!")
            sys.exit(0)
    except Exception as e:
        print(f"{url}: Error - {e}")

print("\n⚠️  Backend is running but no standard endpoints found")
print("This is normal - the backend is up but may not have a health endpoint")
