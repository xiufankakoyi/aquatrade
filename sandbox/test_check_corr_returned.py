#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查后端是否返回 corr_60d 字段
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 80)
print("检查后端返回的字段")
print("=" * 80)

# 无条件筛选
request_data = {
    "date": "2026-02-13",
    "conditions": [],
    "logic": "AND",
    "order_by": [],
    "page": 1,
    "page_size": 3
}

response = requests.post(
    f"{base_url}/api/screener/filter",
    json=request_data,
    timeout=30
)

data = response.json()
if data.get('success'):
    records = data['data']['records']
    if records:
        print(f"\n返回的字段列表:")
        for key in records[0].keys():
            print(f"  - {key}")
        
        print(f"\n第一条数据:")
        print(json.dumps(records[0], indent=2, ensure_ascii=False))
        
        # 检查 corr_60d
        if 'corr_60d' in records[0]:
            print(f"\n✅ corr_60d 字段存在，值: {records[0]['corr_60d']}")
        else:
            print(f"\n❌ corr_60d 字段不存在！")
else:
    print(f"❌ 查询失败: {data.get('error')}")
