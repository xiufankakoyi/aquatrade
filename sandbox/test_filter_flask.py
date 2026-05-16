#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在 Flask 应用上下文中测试 filter_stocks
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("在 Flask 应用上下文中测试 filter_stocks")
print("=" * 70)

# 导入 Flask 应用
from server.app import app

# 在应用上下文中测试
with app.app_context():
    with app.test_client() as client:
        # 测试 filter 接口
        print("\n1. 测试 /api/screener/filter")
        response = client.post('/api/screener/filter', 
                              json={'date': '2026-02-13'},
                              content_type='application/json')
        print(f"   状态码: {response.status_code}")
        
        import json
        data = response.get_json()
        if 'traceback' in data:
            print(f"   Traceback:\n{data['traceback']}")
        else:
            print(f"   响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")

print("\n" + "=" * 70)
