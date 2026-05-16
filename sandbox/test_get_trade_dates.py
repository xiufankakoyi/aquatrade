#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 get_trade_dates() 函数"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

# 模拟 Flask request 对象
class MockRequest:
    args = {}

import flask
app = flask.Flask(__name__)
app.testing = True

with app.app_context():
    from server.routes.screener_routes import get_trade_dates
    
    print("测试 get_trade_dates():")
    result = get_trade_dates()
    print(f"  返回类型: {type(result)}")
    if isinstance(result, tuple):
        print(f"  响应数据: {result[0].get_json()}")
    else:
        print(f"  响应数据: {result.get_json()}")
