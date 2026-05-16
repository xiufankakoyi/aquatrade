#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列出 Flask 应用的所有路由"""
import requests

response = requests.get("http://localhost:5000/")
print(f"Root status: {response.status_code}")

# 尝试访问 indicators 端点
response = requests.get("http://localhost:5000/api/screener/indicators")
print(f"Indicators status: {response.status_code}")

# 尝试访问 debug 端点
response = requests.get("http://localhost:5000/api/screener/debug/source")
print(f"Debug source status: {response.status_code}")
if response.status_code == 200:
    print(response.json())
