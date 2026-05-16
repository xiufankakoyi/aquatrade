#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 2026-02-04 数据
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 80)
print("测试 2026-02-04 无条件筛选")
print("=" * 80)

request_data = {
    "date": "2026-02-04",
    "conditions": [],
    "logic": "AND",
    "order_by": [],
    "page": 1,
    "page_size": 5
}

response = requests.post(
    f"{base_url}/api/screener/filter",
    json=request_data,
    timeout=30
)

data = response.json()
if data.get('success'):
    records = data['data']['records']
    total = data['data']['total']
    print(f"✅ 查询成功！共 {total} 只股票")
    print(f"\n前5只股票:")
    for i, stock in enumerate(records, 1):
        print(f"  {i}. {stock['stock_code']} - 收盘价: {stock['close']}")
else:
    print(f"❌ 查询失败: {data.get('error')}")
