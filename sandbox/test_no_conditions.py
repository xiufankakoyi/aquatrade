#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试无条件筛选（只排序）
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 80)
print("测试无条件筛选（只按相关系数60排序）")
print("=" * 80)

# 无条件，只排序
request_data = {
    "date": "2026-02-04",
    "conditions": [],  # 空条件
    "logic": "AND",
    "order_by": [
        {
            "field": "corr_60d",
            "direction": "asc"  # 升序，找最低的
        }
    ],
    "page": 1,
    "page_size": 5
}

print(f"\n请求参数:")
print(json.dumps(request_data, indent=2, ensure_ascii=False))

try:
    response = requests.post(
        f"{base_url}/api/screener/filter",
        json=request_data,
        timeout=30
    )
    print(f"\n状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            records = data['data']['records']
            total = data['data']['total']
            
            print(f"\n✅ 查询成功！")
            print(f"符合条件的股票总数: {total}")
            print(f"\n相关系数(60)最低的5只股票:")
            print("-" * 80)
            
            for i, stock in enumerate(records, 1):
                corr = stock.get('corr_60d', 'N/A')
                print(f"\n第 {i} 名:")
                print(f"  股票代码: {stock['stock_code']}")
                print(f"  收盘价: {stock['close']:.2f} 元")
                print(f"  相关系数(60): {corr}")
        else:
            print(f"❌ 查询失败: {data.get('error')}")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        print(f"响应: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
