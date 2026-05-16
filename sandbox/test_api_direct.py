#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试 API 响应
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json

# 直接调用 API 函数
from core.portfolio.position_manager import PositionManager
from core.portfolio.signal_engine import SignalEngine

pm = PositionManager()
positions = pm.get_all_positions(active_only=True)

print(f'持仓数量: {len(positions)}')

if positions:
    signal_engine = SignalEngine()
    stock_codes = [p.stock_code for p in positions]
    latest_prices = signal_engine.get_latest_prices(stock_codes)
    
    analysis = pm.calculate_analysis(positions, latest_prices)
    
    # 获取行业分布
    industry_dist = pm.get_industry_distribution_from_dict(analysis['positions'])
    
    print(f'\n行业分布数据: {industry_dist}')
    print(f'\n准备返回给前端的数据:')
    print(json.dumps(industry_dist, ensure_ascii=False, indent=2))
    
    # 模拟 API 返回的完整数据结构
    response_data = {
        'success': True,
        'data': {
            'positions': analysis['positions'],
            'summary': analysis['summary'],
            'industry_distribution': industry_dist
        }
    }
    print(f'\n完整 API 响应:')
    print(json.dumps(response_data, ensure_ascii=False, indent=2, default=str))
else:
    print('没有持仓数据')
