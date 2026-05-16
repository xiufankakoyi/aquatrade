#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 screener_routes 中的函数"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from server.routes.screener_routes import get_stock_daily_df

result = get_stock_daily_df()
print(f'Result type: {type(result)}')
if result is not None:
    print(f'Has empty attr: {hasattr(result, "empty")}')
    print(f'Result class: {result.__class__}')
    print(f'Result module: {result.__class__.__module__}')
