"""
检查数据时间范围
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox.data_cache import get_cache

data = get_cache()

all_dates = []
for stock_code in data.stock_codes:
    stock_data = data.daily_data.get(stock_code)
    if stock_data:
        all_dates.extend(stock_data['dates'].tolist())

all_dates = sorted(set(all_dates))

print(f"\n数据时间范围:")
print(f"  最早日期: {all_dates[0]}")
print(f"  最晚日期: {all_dates[-1]}")
print(f"  总交易日: {len(all_dates)}")

print(f"\n按年份分布:")
years = {}
for d in all_dates:
    year = d[:4]
    years[year] = years.get(year, 0) + 1

for year in sorted(years.keys()):
    print(f"  {year}: {years[year]} 天")
