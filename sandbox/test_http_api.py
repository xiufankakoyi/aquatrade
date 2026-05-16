#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 HTTP API 端点
"""
import requests
import json

base_url = "http://localhost:5000"

# 测试 filter API
print("Testing filter with date=2026-02-04")
try:
    response = requests.post(
        f"{base_url}/api/screener/filter",
        json={
            "date": "2026-02-04",
            "conditions": [{"field": "rsi_6", "operator": ">", "value": 70}],
            "logic": "AND",
            "page": 1,
            "page_size": 20
        },
        timeout=30
    )
    print(f"Status: {response.status_code}")
    
    # 直接解析 JSON
    data = response.json()
    print(f"\n成功! 找到 {data['data']['total']} 条记录")
    print(f"总页数: {data['data']['total_pages']}")
    print(f"当前页记录数: {len(data['data']['records'])}")
    print(f"\n第一条记录:")
    print(json.dumps(data['data']['records'][0], indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
