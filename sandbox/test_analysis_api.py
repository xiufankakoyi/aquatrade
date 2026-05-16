import requests

BASE_URL = "http://localhost:5000"

print("测试 /api/portfolio/analysis 接口...")
response = requests.get(f"{BASE_URL}/api/portfolio/analysis")
data = response.json()

if data.get('success'):
    result = data.get('data', {})
    print(f"positions 数量: {len(result.get('positions', []))}")
    print(f"summary: {result.get('summary', {})}")
    print(f"industry_distribution: {result.get('industry_distribution', {})}")

    if result.get('positions'):
        p = result['positions'][0]
        print(f"\n第一条持仓数据:")
        print(f"  id: {p.get('id')}")
        print(f"  stock_code: {p.get('stock_code')}")
        print(f"  stock_name: {p.get('stock_name')}")
        print(f"  keys: {list(p.keys())}")
else:
    print(f"Error: {data}")
