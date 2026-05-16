#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 field_stats API 端点 - 边界情况
"""
import requests
import json

base_url = "http://localhost:5000"

# 测试 1: 正常字段
print("Test 1: 正常字段 rsi_6")
response = requests.post(
    f"{base_url}/api/screener/field_stats",
    json={"field": "rsi_6", "date": "2026-02-04"},
    timeout=10
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:200]}")

# 测试 2: 无效字段
print("\nTest 2: 无效字段 invalid_field")
response = requests.post(
    f"{base_url}/api/screener/field_stats",
    json={"field": "invalid_field", "date": "2026-02-04"},
    timeout=10
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# 测试 3: 空字段
print("\nTest 3: 空字段")
response = requests.post(
    f"{base_url}/api/screener/field_stats",
    json={"field": "", "date": "2026-02-04"},
    timeout=10
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# 测试 4: 无日期（使用最新日期）
print("\nTest 4: 无日期参数")
response = requests.post(
    f"{base_url}/api/screener/field_stats",
    json={"field": "rsi_6"},
    timeout=10
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:200]}")

# 测试 5: 无效日期
print("\nTest 5: 无效日期 2025-01-01")
response = requests.post(
    f"{base_url}/api/screener/field_stats",
    json={"field": "rsi_6", "date": "2025-01-01"},
    timeout=10
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
