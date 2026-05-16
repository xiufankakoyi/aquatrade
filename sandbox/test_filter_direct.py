#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json

def test_filter_direct():
    """直接测试筛选API，打印完整响应"""
    try:
        print("=" * 60)
        print("测试 /api/screener/filter")
        print("=" * 60)
        
        params = {
            "date": "2025-11-20",
            "conditions": [],
            "logic": "AND",
            "order_by": [],
            "page": 1,
            "page_size": 20
        }
        
        print(f"请求参数: {json.dumps(params, indent=2, ensure_ascii=False)}")
        print()
        
        r = requests.post(
            'http://localhost:5000/api/screener/filter',
            json=params,
            timeout=60
        )
        
        print(f"状态码: {r.status_code}")
        print(f"响应头: {dict(r.headers)}")
        print()
        
        data = r.json()
        print(f"完整响应:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_filter_direct()
