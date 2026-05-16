#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试筛选含数字1的股票代码，按股价排序前3只
预期结果：贵州茅台、北方华创、炬光科技
"""
import requests
import json

base_url = "http://localhost:5000"

print("=" * 60)
print("测试：筛选含数字1的股票代码，按收盘价降序排序前3只")
print("=" * 60)

# 构建筛选请求
# 条件：stock_code 包含 '1'
# 排序：close 降序
# 分页：前3条
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
    "page_size": 3
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
            print(f"\n前3只股价最高的股票（含数字1）:")
            print("-" * 80)
            
            for i, stock in enumerate(records, 1):
                print(f"\n第 {i} 名:")
                print(f"  股票代码: {stock['stock_code']}")
                print(f"  收盘价: {stock['close']} 元")
                print(f"  涨跌幅: {stock.get('change_pct', 'N/A')}%")
                print(f"  成交额: {stock.get('amount', 'N/A')} 元")
                print(f"  总市值: {stock.get('total_mv', 'N/A')}")
                
            # 验证预期结果
            print("\n" + "=" * 80)
            print("预期结果验证:")
            expected = ["贵州茅台", "北方华创", "炬光科技"]
            actual_codes = [s['stock_code'] for s in records]
            print(f"实际返回的股票代码: {actual_codes}")
            print(f"\n注：需要确认这些代码对应的股票名称是否为:")
            for name in expected:
                print(f"  - {name}")
        else:
            print(f"❌ 查询失败: {data.get('error')}")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        print(f"响应: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
