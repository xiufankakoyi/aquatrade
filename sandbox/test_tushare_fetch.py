#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Tushare API 获取数据
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import Config
import tushare as ts

print(f"Tushare Token: {Config.TUSHARE_TOKEN[:10]}..." if Config.TUSHARE_TOKEN else "Token 未配置")

if Config.TUSHARE_TOKEN:
    pro = ts.pro_api(Config.TUSHARE_TOKEN)
    
    # 测试获取交易日历
    print("\n测试获取交易日历...")
    try:
        df = pro.trade_cal(exchange='SSE', start_date='20260201', end_date='20260228')
        print(f"获取到 {len(df)} 条交易日历数据")
        print(df.head())
    except Exception as e:
        print(f"获取交易日历失败: {e}")
    
    # 测试获取日线数据
    print("\n测试获取 2026-02-13 日线数据...")
    try:
        df = pro.daily(trade_date='20260213')
        print(f"获取到 {len(df)} 条日线数据")
        print(df.head())
    except Exception as e:
        print(f"获取日线数据失败: {e}")
    
    # 测试获取每日指标
    print("\n测试获取 2026-02-13 每日指标...")
    try:
        df = pro.daily_basic(trade_date='20260213')
        print(f"获取到 {len(df)} 条每日指标数据")
        print(df.head())
    except Exception as e:
        print(f"获取每日指标失败: {e}")
else:
    print("请先配置 TUSHARE_TOKEN")
