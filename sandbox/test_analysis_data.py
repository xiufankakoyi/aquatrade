"""
检查 analysis 接口返回的数据结构
"""
import requests

resp = requests.get('http://localhost:5000/api/portfolio/analysis')
data = resp.json()

if data.get('success'):
    positions = data['data']['positions']
    print(f"持仓数量: {len(positions)}")
    for p in positions:
        print(f"  ID={p['id']} (type: {type(p['id'])}): {p['stock_code']} {p['stock_name']}")
