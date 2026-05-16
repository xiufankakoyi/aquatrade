#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试导入 screener_routes 模块"""
import sys
sys.path.insert(0, '.')

# 清除缓存
for mod in list(sys.modules.keys()):
    if 'screener' in mod:
        del sys.modules[mod]

from server.routes.screener_routes import INDICATOR_CATEGORIES

print("INDICATOR_CATEGORIES['basic']:")
for indicator in INDICATOR_CATEGORIES['basic']['indicators']:
    print(f"  - {indicator}")
