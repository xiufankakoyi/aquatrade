#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 get_stock_daily_df() 函数使用 Polars"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from server.routes.screener_routes import get_stock_daily_df

df = get_stock_daily_df()
print(f"返回类型: {type(df)}")
if df is not None:
    print(f"数据形状: {df.shape}")
    print(f"列名: {df.columns[:10]}")
    print(f"trade_date 列是否存在: {'trade_date' in df.columns}")
    if 'trade_date' in df.columns:
        dates = df.select('trade_date').unique().to_series().to_list()
        print(f"唯一日期数量: {len(dates)}")
        print(f"前5个日期: {dates[:5]}")
else:
    print("返回 None")
