#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查股票价格
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_query import get_stock_daily_latest

# 检查这些股票的价格
prices = get_stock_daily_latest()
if prices is not None:
    print('最新交易日价格数据:')
    for code in ['603256', '600941', '000066', '513050', '009690']:
        row = prices[prices['stock_code'] == code]
        if not row.empty:
            close_price = row.iloc[0]['close']
            print(f'  {code}: 收盘价={close_price}')
        else:
            print(f'  {code}: 未找到价格数据')
else:
    print('无法获取价格数据')
