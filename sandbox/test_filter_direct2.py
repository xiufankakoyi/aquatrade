#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试 filter_stocks 函数
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("直接测试 filter_stocks 函数")
print("=" * 70)

# 模拟 Flask 请求
class MockRequest:
    def get_json(self):
        return {'date': '2026-02-13'}

# 导入并测试
from server.routes.screener_routes import filter_stocks

# 替换 request
import server.routes.screener_routes as screener_module
original_request = screener_module.request

class MockRequestObj:
    pass

mock_request = MockRequestObj()
mock_request.get_json = lambda: {'date': '2026-02-13'}

screener_module.request = mock_request

try:
    result = filter_stocks()
    print(f"\n结果类型: {type(result)}")
    print(f"状态码: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
    if hasattr(result, 'get_json'):
        data = result.get_json()
        print(f"响应数据: {data}")
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
finally:
    screener_module.request = original_request

print("\n" + "=" * 70)
