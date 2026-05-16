#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查交易日历
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

# 获取交易日历
data_query = OptimizedStockDataQuery(warmup=False)
dates = data_query.get_trading_dates()

print(f"交易日历范围: {dates[0]} ~ {dates[-1]}")
print(f"总交易日数: {len(dates)}")
print()

# 查看最近20个交易日
print("最近20个交易日:")
for date in dates[-20:]:
    print(f"  {date}")

# 检查2026-02-13之后是否有交易日
dates_after_feb13 = [d for d in dates if d > '20260213']
print()
print(f"2026-02-13之后的交易日数量: {len(dates_after_feb13)}")
if dates_after_feb13:
    print(f"  下一个交易日: {dates_after_feb13[0]}")
else:
    print("  没有更多交易日数据")
