"""
直接测试后端 API 是否正常工作
"""
import requests
import json

# 测试 kline API
print("=== Testing /api/kline ===")
url = "http://localhost:5000/api/kline?symbol=000300&start=2024-01-01&end=2024-12-31"
print(f"URL: {url}")

try:
    r = requests.get(url, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    
    # 尝试解析 JSON
    try:
        data = r.json()
        print(f"Response type: {type(data)}")
        if isinstance(data, list):
            print(f"List length: {len(data)}")
            if data:
                print(f"First item: {data[0]}")
        elif isinstance(data, dict):
            print(f"Dict keys: {data.keys()}")
            if 'data' in data:
                print(f"Data length: {len(data['data'])}")
                if data['data']:
                    print(f"First item: {data['data'][0]}")
        else:
            print(f"Raw response: {data}")
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"Raw text: {r.text[:500]}")
        
except Exception as e:
    print(f"Request error: {e}")

# 测试直接调用 visualization_api
print("\n=== Testing visualization_api directly ===")
import sys
sys.path.insert(0, '.')

from server.app import get_api
api = get_api()

# 测试 get_symbol_kline
print("\nCalling get_symbol_kline('000300', '2024-01-01', '2024-12-31')...")
result = api.get_symbol_kline('000300', '2024-01-01', '2024-12-31')
print(f"Result count: {len(result)}")
if result:
    print(f"First: {result[0]}")
else:
    print("Empty result!")
    
# 测试 _get_index_kline_from_parquet
print("\nCalling _get_index_kline_from_parquet('000300', '2024-01-01', '2024-12-31')...")
result2 = api._get_index_kline_from_parquet('000300', '2024-01-01', '2024-12-31')
print(f"Result count: {len(result2)}")
if result2:
    print(f"First: {result2[0]}")
else:
    print("Empty result!")
