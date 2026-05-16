#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找炬光科技的股票代码
"""
import requests

base_url = "http://localhost:5000"

# 查询所有含数字1的股票，按股价排序，查看前10只
request_data = {
    "date": "2026-02-04",
    "conditions": [
        {
            "field": "stock_code",
            "operator": "contains",
            "value": "1"
        }
    ],
    "logic": "AND",
    "order_by": [
        {
            "field": "close",
            "direction": "desc"
        }
    ],
    "page": 1,
    "page_size": 10
}

response = requests.post(
    f"{base_url}/api/screener/filter",
    json=request_data,
    timeout=30
)

data = response.json()
if data.get('success'):
    records = data['data']['records']
    print("含数字1的股票中，股价前10名：")
    print("-" * 80)
    for i, stock in enumerate(records, 1):
        print(f"{i}. 股票代码: {stock['stock_code']}, 收盘价: {stock['close']} 元")
        
# 尝试搜索炬光科技（可能代码包含167）
print("\n" + "=" * 80)
print("\n搜索代码包含167的股票（炬光科技可能是688167）：")
request_data2 = {
    "date": "2026-02-04",
    "conditions": [
        {
            "field": "stock_code",
            "operator": "contains",
            "value": "167"
        }
    ],
    "logic": "AND",
    "order_by": [
        {
            "field": "close",
            "direction": "desc"
        }
    ],
    "page": 1,
    "page_size": 5
}

response = requests.post(
    f"{base_url}/api/screener/filter",
    json=request_data2,
    timeout=30
)

data = response.json()
if data.get('success'):
    records = data['data']['records']
    for stock in records:
        print(f"股票代码: {stock['stock_code']}, 收盘价: {stock['close']} 元")
