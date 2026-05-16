#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json

def test_trade_dates():
    """测试交易日 API"""
    try:
        print("正在测试 /api/screener/dates ...")
        r = requests.get('http://localhost:5000/api/screener/dates', timeout=30)
        print(f"状态码: {r.status_code}")
        data = r.json()
        print(f"返回数据: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")
        
        if data.get('success') and data.get('data', {}).get('dates'):
            dates = data['data']['dates']
            print(f"\n✓ 成功获取 {len(dates)} 个交易日")
            print(f"最新日期: {data['data'].get('latest', 'N/A')}")
            print(f"前5个日期: {dates[:5]}")
        else:
            print(f"\n✗ 未获取到交易日数据")
            print(f"错误: {data.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")

if __name__ == '__main__':
    test_trade_dates()
