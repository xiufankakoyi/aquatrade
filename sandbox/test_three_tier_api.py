"""测试三层架构 API"""
import requests
import json

# 测试 K 线数据 API
url = "http://localhost:5000/api/kline"
params = {
    "symbol": "000001.SZ",
    "start": "2024-01-01",
    "end": "2024-12-31"
}

try:
    print("测试三层架构 K 线 API...")
    print(f"URL: {url}")
    print(f"参数: {params}")
    print()
    
    response = requests.get(url, params=params, timeout=10)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            kline_data = data.get("data", [])
            print(f"✅ 成功获取 {len(kline_data)} 条 K 线数据")
            if kline_data:
                print(f"\n第一条数据:")
                print(json.dumps(kline_data[0], indent=2, ensure_ascii=False))
                print(f"\n最后一条数据:")
                print(json.dumps(kline_data[-1], indent=2, ensure_ascii=False))
        else:
            print(f"❌ API 返回错误: {data.get('error')}")
    else:
        print(f"❌ 请求失败: {response.text}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
