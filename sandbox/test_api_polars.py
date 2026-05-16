#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 API 响应"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

import requests
response = requests.get("http://localhost:5000/api/screener/dates")
print(f"状态码: {response.status_code}")
data = response.json()
print(f"响应内容: {data}")
print(f"日期数量: {len(data['data']['dates'])}")
print(f"最近日期: {data['data']['latest']}")
if data['data']['dates']:
    print(f"前5个日期: {data['data']['dates'][:5]}")
