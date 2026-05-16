"""
调试符号列表
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import arcticdb as adb

print("=" * 80)
print("调试符号列表")
print("=" * 80)

arctic = adb.Arctic("lmdb://./data/arctic_db?map_size=20GB")
lib = arctic['stock_daily']

print("\n1. 获取所有符号...")
try:
    symbols = lib.list_symbols()
    print(f"符号数: {len(symbols)}")
    
    print("\n2. 过滤 2024-01 到 2024-03 的符号:")
    start_year = 2024
    start_month = 1
    end_year = 2024
    end_month = 3
    
    needed_months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        needed_months.append(f"month_{y}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    
    print(f"需要的月份: {needed_months}")
    
    matched = [s for s in symbols if s in needed_months]
    print(f"匹配的符号: {matched}")
    
    print("\n3. 尝试读取每个匹配的符号:")
    for sym in matched:
        try:
            result = lib.read(sym)
            print(f"  {sym}: {len(result.data)} 行")
        except Exception as e:
            print(f"  {sym}: 读取失败 - {e}")
            
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
