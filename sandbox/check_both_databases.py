#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查两个 ArcticDB 数据库的内容
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arcticdb import Arctic

print("=" * 70)
print("检查两个 ArcticDB 数据库")
print("=" * 70)

# 检查两个路径
paths = [
    ("./data/arctic_db", "主数据库"),
    ("./server/data/arctic_db", "服务器数据库")
]

for path, name in paths:
    print(f"\n{'='*70}")
    print(f"{name}: {path}")
    print("=" * 70)
    
    try:
        arctic = Arctic(f"lmdb://{path}")
        libraries = arctic.list_libraries()
        print(f"库数量: {len(libraries)}")
        print(f"库列表: {libraries}")
        
        # 检查 stock_daily 库
        if "stock_daily" in libraries:
            lib = arctic["stock_daily"]
            symbols = lib.list_symbols()
            print(f"\nstock_daily 库:")
            print(f"  Symbols: {symbols}")
            
            if "stock_daily" in symbols:
                data = lib.read("stock_daily")
                df = data.data
                print(f"  记录数: {len(df):,}")
                if hasattr(df, 'columns') and 'trade_date' in df.columns:
                    print(f"  日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        
        # 检查 market_data 库
        if "market_data" in libraries:
            lib = arctic["market_data"]
            symbols = lib.list_symbols()
            print(f"\nmarket_data 库:")
            print(f"  股票数: {len(symbols)}")
    
    except Exception as e:
        print(f"错误: {e}")

print("\n" + "=" * 70)
print("建议:")
print("=" * 70)
print("如果服务器数据库 (server/data/arctic_db) 数据不完整，")
print("建议删除它，让服务器使用主数据库 (data/arctic_db)")
print("=" * 70)
