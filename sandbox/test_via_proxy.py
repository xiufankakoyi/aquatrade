#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试通过前端代理访问 API
"""
import requests
import json

# 通过前端代理访问
base_url = "http://localhost:5173"

# 测试 field_stats API - POST 方法
print("Testing field_stats via frontend proxy (port 5173)")
try:
    response = requests.post(
        f"{base_url}/api/screener/field_stats",
        json={"field": "rsi_6", "date": "2026-02-04"},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

# 直接访问后端
base_url_direct = "http://localhost:5000"
print("Testing field_stats directly (port 5000)")
try:
    response = requests.post(
        f"{base_url_direct}/api/screener/field_stats",
        json={"field": "rsi_6", "date": "2026-02-04"},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
