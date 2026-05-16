#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试股票筛选器 API - 使用正确的日期"""
import requests
import json

BASE_URL = "http://localhost:5173/api/screener"

def test_filter_with_correct_date():
    """测试筛选接口 - 使用数据库中存在的日期"""
    print("=" * 50)
    print("测试 /filter 接口 - 使用正确的日期")
    print("=" * 50)
    
    # 先获取可用日期
    dates_res = requests.get(f"{BASE_URL}/dates")
    if dates_res.status_code == 200:
        dates_data = dates_res.json()
        available_dates = dates_data.get('data', {}).get('dates', [])
        print(f"可用日期: {available_dates[:5]}...")
        
        if available_dates:
            test_date = available_dates[0]  # 使用最新的日期
            print(f"使用日期: {test_date}")
            
            payload = {
                "date": test_date,
                "conditions": [],
                "logic": "AND",
                "order_by": [],
                "page": 1,
                "page_size": 20
            }
            
            response = requests.post(f"{BASE_URL}/filter", json=payload)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.text[:1000] if len(response.text) > 1000 else response.text}")
            return response.status_code == 200
    
    return False

if __name__ == "__main__":
    success = test_filter_with_correct_date()
    print(f"\n测试{'通过' if success else '失败'}")
