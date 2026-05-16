#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 field_stats API 端点
"""
import requests
import json

base_url = "http://localhost:5000"

# 测试 field_stats API - POST 方法
print("Testing field_stats with POST method")
try:
    response = requests.post(
        f"{base_url}/api/screener/field_stats",
        json={"field": "rsi_6", "date": "2026-02-04"},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        data = response.json()
        print(f"\n成功!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
