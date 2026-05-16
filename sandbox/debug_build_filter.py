#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试 build_filter_sql 函数"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

# 强制重新加载模块
import importlib
import server.routes.screener_routes as screener_module
importlib.reload(screener_module)

from server.routes.screener_routes import build_filter_sql

# 打印函数源代码
import inspect
print("build_filter_sql 源代码:")
print(inspect.getsource(build_filter_sql))

# 测试函数
conditions = [{"field": "rsi_6", "operator": ">", "value": 70}]
result = build_filter_sql(conditions, "AND")
print(f"\n测试结果: {result}")
print(f"结果类型: {type(result)}")
