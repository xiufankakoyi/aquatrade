#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 HTTP API
"""
import requests
import json

BASE_URL = "http://localhost:5000"

# 测试获取交易日
print("=== 测试获取交易日 ===")
try:
    resp = requests.get(f"{BASE_URL}/api/screener/dates", timeout=10)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
    else:
        print(f"错误: {resp.text}")
except Exception as e:
    print(f"请求失败: {e}")

# 测试筛选接口
print("\n=== 测试筛选接口（无条件） ===")
try:
    resp = requests.post(
        f"{BASE_URL}/api/screener/filter",
        json={"date": "2026-02-13", "conditions": [], "page": 1, "page_size": 10},
        timeout=30
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if data.get('success'):
            print(f"总数: {data['data']['total']}")
            print(f"返回记录数: {len(data['data']['records'])}")
            if data['data']['records']:
                print(f"第一条记录: {json.dumps(data['data']['records'][0], indent=2, ensure_ascii=False)}")
        else:
            print(f"错误: {data.get('error')}")
    else:
        print(f"错误: {resp.text}")
except Exception as e:
    print(f"请求失败: {e}")
