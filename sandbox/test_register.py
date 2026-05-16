#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试路由注册"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

from flask import Flask
app = Flask(__name__)

try:
    from server.routes.screener_routes import screener_bp
    print(f"Loaded screener_bp: {screener_bp}")
    app.register_blueprint(screener_bp)
    print("Registered successfully!")
    
    # 列出所有路由
    print("\nRoutes:")
    for rule in app.url_map.iter_rules():
        if 'screener' in rule.endpoint:
            print(f"  {rule.rule} -> {rule.endpoint}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
