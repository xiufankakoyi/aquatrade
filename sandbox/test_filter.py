#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json

def test_filter():
    """测试筛选API"""
    try:
        # 测试无条件筛选（应该返回所有股票）
        print("正在测试 /api/screener/filter ...")
        params = {
            "date": "2025-11-20",
            "conditions": [],
            "logic": "AND",
            "order_by": [],
            "page": 1,
            "page_size": 20
        }
        
        r = requests.post(
            'http://localhost:5000/api/screener/filter',
            json=params,
            timeout=30
        )
        print(f"状态码: {r.status_code}")
        data = r.json()
        
        if data.get('success'):
            records = data.get('data', {}).get('records', [])
            total = data.get('data', {}).get('total', 0)
            print(f"\n✓ 成功获取数据")
            print(f"总记录数: {total}")
            print(f"本页记录数: {len(records)}")
            
            if records:
                print(f"\n前5条记录:")
                for i, record in enumerate(records[:5]):
                    print(f"  {i+1}. {record.get('stock_code', 'N/A')} - {record.get('trade_date', 'N/A')}")
        else:
            print(f"\n✗ 请求失败")
            print(f"错误: {data.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_filter()
