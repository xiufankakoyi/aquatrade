#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试筛选器返回的前复权价格
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 80)
print("测试筛选器返回的前复权价格")
print("=" * 80)

# 查询含数字1的股票，按收盘价降序排序
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
    "page_size": 5
}

response = requests.post(
    f"{base_url}/api/screener/filter",
    json=request_data,
    timeout=30
)

data = response.json()
if data.get('success'):
    records = data['data']['records']
    print("\n筛选器返回的前5只股票（含数字1，按收盘价降序）：")
    print("-" * 80)
    print(f"{'排名':<6}{'股票代码':<12}{'收盘价':<15}{'复权因子':<12}{'涨跌幅':<10}")
    print("-" * 80)
    
    for i, stock in enumerate(records, 1):
        print(f"{i:<6}{stock['stock_code']:<12}{stock['close']:<15.2f}{stock.get('adj_factor', 'N/A'):<12}{stock.get('change_pct', 'N/A'):<10}")
    
    print("\n" + "=" * 80)
    print("\n手动验证前复权价格计算：")
    print("前复权价 = 除权价 × (当日复权因子 / 最新复权因子)")
    print("\n对于 2026-02-04 的数据：")
    print("- 当日复权因子 = 最新复权因子（因为是最新数据）")
    print("- 所以前复权价 = 除权价")
    print("\n如果要看到真正的前复权效果，需要查询历史日期，比如 2025-01-02")
    
    # 查询历史日期
    print("\n" + "=" * 80)
    print("\n查询历史日期 2025-01-02 的数据：")
    request_data2 = {
        "date": "2025-01-02",
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
        "page_size": 5
    }
    
    response2 = requests.post(
        f"{base_url}/api/screener/filter",
        json=request_data2,
        timeout=30
    )
    
    data2 = response2.json()
    if data2.get('success'):
        records2 = data2['data']['records']
        print(f"\n{'排名':<6}{'股票代码':<12}{'收盘价':<15}{'复权因子':<12}{'涨跌幅':<10}")
        print("-" * 80)
        for i, stock in enumerate(records2, 1):
            print(f"{i:<6}{stock['stock_code']:<12}{stock['close']:<15.2f}{stock.get('adj_factor', 'N/A'):<12}{stock.get('change_pct', 'N/A'):<10}")
else:
    print(f"❌ 查询失败: {data.get('error')}")
