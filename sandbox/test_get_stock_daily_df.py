#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 get_stock_daily_df() 函数"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

# 模拟 Flask request 对象
class MockRequest:
    args = {}

import flask
app = flask.Flask(__name__)
app.testing = True

with app.app_context():
    from server.routes.screener_routes import get_stock_daily_df, get_trade_dates
    
    print("测试 get_stock_daily_df():")
    df = get_stock_daily_df()
    print(f"  返回类型: {type(df)}")
    if df is not None:
        print(f"  数据形状: {df.shape}")
        print(f"  列名: {df.columns.tolist()[:5]}")
        print(f"  trade_date 列是否存在: {'trade_date' in df.columns}")
        if 'trade_date' in df.columns:
            dates = df['trade_date'].dropna().unique().tolist()
            print(f"  唯一日期数量: {len(dates)}")
            print(f"  最近的日期: {dates[0] if dates else 'N/A'}")
    else:
        print("  返回 None")
