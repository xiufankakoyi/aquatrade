#!/usr/bin/env python
import requests

r = requests.post('http://localhost:5000/api/screener/filter', 
    json={'date': '2025-11-20', 'conditions': [], 'logic': 'AND', 'order_by': [], 'page': 1, 'page_size': 100},
    timeout=60)
data = r.json()
print(f"总记录数: {data['data']['total']}")
print(f"返回记录数: {len(data['data']['records'])}")
for r in data['data']['records'][:5]:
    print(f"  - {r['stock_code']}")
