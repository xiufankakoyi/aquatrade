#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查当前加载的模块源代码"""
import requests
import json

# 调用一个特殊的端点来检查模块源代码
response = requests.get("http://localhost:5000/api/debug/source")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(response.text)
else:
    print("Debug endpoint not available")
