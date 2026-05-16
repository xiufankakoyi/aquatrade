import requests

# 获取所有持仓
url = 'http://localhost:5000/api/portfolio/analysis'
response = requests.get(url)
data = response.json()

if data['success']:
    positions = data['data']['positions']
    print(f'总持仓数量: {len(positions)}')
    print()
    for p in positions:
        print(f"{p['stock_code']} {p['stock_name']}")
        print(f"  买入价: {p['buy_price']}, 数量: {p['shares']}, 成本: {p['cost']:.2f}")
        print()
else:
    print(f'Error: {data}')
