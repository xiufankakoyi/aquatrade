#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 2026-02-13 无条件筛选
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 80)
print("测试 2026-02-13 无条件筛选")
print("=" * 80)

request_data = {
    "date": "2026-02-13",
    "conditions": [],
    "logic": "AND",
    "order_by": [],
    "page": 1,
    "page_size": 20
}

print(f"\n请求参数:")
print(json.dumps(request_data, indent=2, ensure_ascii=False))

try:
    response = requests.post(
        f"{base_url}/api/screener/filter",
        json=request_data,
        timeout=30
    )
    print(f"\n状态码: {response.status_code}")
    
    data = response.json()
    print(f"\n响应:")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    
except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
