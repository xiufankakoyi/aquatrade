#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 API 响应"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

import requests
response = requests.get("http://localhost:5000/api/screener/dates")
print(f"状态码: {response.status_code}")
print(f"响应内容: {response.json()}")
