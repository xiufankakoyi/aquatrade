#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 stock_basic 数据
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_query import get_stock_basic

df = get_stock_basic()
if df is not None and not df.empty:
    # 检查特定股票
    for code in ['009690', '513050', '603256', '600941', '000066']:
        row = df[df['code'] == code]
        if not row.empty:
            print(f'{code}: industry={row.iloc[0].get("industry", "N/A")}, name={row.iloc[0].get("name", "N/A")}')
        else:
            print(f'{code}: 未找到')
else:
    print('无法获取数据')
