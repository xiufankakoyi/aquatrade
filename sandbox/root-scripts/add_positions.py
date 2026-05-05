"""
添加持仓数据
"""
import requests

BASE_URL = 'http://localhost:5000'

positions = [
    {
        'stock_code': '009690',
        'stock_name': '易方达瑞锦C',
        'buy_price': 1.366,
        'shares': 146412.88,
        'cost': 200000.0,
        'buy_date': '2026-02-12',
        'notes': ''
    },
    {
        'stock_code': '513050',
        'stock_name': '中概互联ETF',
        'buy_price': 1.372,
        'shares': 72800,
        'cost': 72800 * 1.372,
        'buy_date': '2026-02-12',
        'notes': ''
    },
    {
        'stock_code': '603256',
        'stock_name': '宏盛电子',
        'buy_price': 75.008,
        'shares': 700,
        'cost': 700 * 75.008,
        'buy_date': '2026-02-12',
        'notes': ''
    },
    {
        'stock_code': '000066',
        'stock_name': '中国长城',
        'buy_price': 16.411,
        'shares': 1800,
        'cost': 1800 * 16.411,
        'buy_date': '2026-02-12',
        'notes': ''
    },
    {
        'stock_code': '600941',
        'stock_name': '中国移动',
        'buy_price': 93.708,
        'shares': 300,
        'cost': 300 * 93.708,
        'buy_date': '2026-02-12',
        'notes': ''
    }
]

for pos in positions:
    resp = requests.post(f'{BASE_URL}/api/portfolio/positions', json=pos)
    result = resp.json()
    if result.get('success'):
        print(f"✅ 添加成功: {pos['stock_code']} {pos['stock_name']}")
    else:
        print(f"❌ 添加失败: {pos['stock_code']} - {result.get('error')}")

print("\n=== 当前持仓 ===")
resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
positions = resp.json().get('data', [])
for p in positions:
    print(f"  {p['stock_code']} {p['stock_name']}: {p['shares']}股 @ {p['buy_price']}")
