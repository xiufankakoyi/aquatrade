#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试行业分布功能
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.portfolio.position_manager import PositionManager
from core.portfolio.signal_engine import SignalEngine

pm = PositionManager()

# 获取持仓
positions = pm.get_all_positions(active_only=True)
print(f'持仓数量: {len(positions)}')

if positions:
    # 获取价格数据
    signal_engine = SignalEngine()
    stock_codes = [p.stock_code for p in positions]
    latest_prices = signal_engine.get_latest_prices(stock_codes)
    
    print(f'价格数据: {latest_prices}')
    
    # 计算分析
    analysis = pm.calculate_analysis(positions, latest_prices)
    
    print(f'\n分析后的持仓数量: {len(analysis["positions"])}')
    for pos in analysis['positions'][:3]:
        print(f'  {pos["stock_code"]}: 市值={pos.get("market_value")}')
    
    # 获取行业分布
    industry_dist = pm.get_industry_distribution_from_dict(analysis['positions'])
    print(f'\n行业分布: {industry_dist}')
else:
    print('没有持仓数据')
