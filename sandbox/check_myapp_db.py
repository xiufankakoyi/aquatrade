#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 myapp/data/arctic_db 的内容
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arcticdb import Arctic

print("=" * 70)
print("检查 myapp/data/arctic_db")
print("=" * 70)

try:
    arctic = Arctic("lmdb://./myapp/data/arctic_db")
    libraries = arctic.list_libraries()
    print(f"库数量: {len(libraries)}")
    print(f"库列表: {libraries}")
    
    # 检查 stock_daily
    if "stock_daily" in libraries:
        lib = arctic["stock_daily"]
        symbols = lib.list_symbols()
        print(f"\nstock_daily 库 symbols: {symbols}")
        
        if "stock_daily" in symbols:
            data = lib.read("stock_daily")
            df = data.data
            print(f"记录数: {len(df):,}")
            if hasattr(df, 'columns') and 'trade_date' in df.columns:
                print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
    else:
        print("\n⚠️  没有 stock_daily 库")
        
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 70)
print("对比主数据库 (data/arctic_db)")
print("=" * 70)

try:
    main_arctic = Arctic("lmdb://./data/arctic_db")
    main_libs = main_arctic.list_libraries()
    print(f"主数据库库数量: {len(main_libs)}")
    
    if "stock_daily" in main_libs:
        lib = main_arctic["stock_daily"]
        data = lib.read("stock_daily")
        df = data.data
        print(f"stock_daily 记录数: {len(df):,}")
        if hasattr(df, 'columns') and 'trade_date' in df.columns:
            print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 70)
