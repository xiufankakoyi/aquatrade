#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细检查服务器数据库的内容
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arcticdb import Arctic
import pandas as pd

print("=" * 70)
print("详细检查服务器数据库 (server/data/arctic_db)")
print("=" * 70)

arctic = Arctic("lmdb://./server/data/arctic_db")
libraries = arctic.list_libraries()

print(f"\n库数量: {len(libraries)}")

for lib_name in libraries:
    print(f"\n{'='*70}")
    print(f"库: {lib_name}")
    print("=" * 70)
    
    lib = arctic[lib_name]
    symbols = lib.list_symbols()
    print(f"Symbols ({len(symbols)} 个):")
    
    for symbol in symbols[:5]:  # 只显示前5个
        try:
            data = lib.read(symbol)
            df = data.data
            print(f"  - {symbol}: {len(df):,} 行", end="")
            
            if hasattr(df, 'columns'):
                if 'trade_date' in df.columns:
                    print(f", 日期: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
                elif hasattr(df, 'index') and 'trade_date' in str(df.index):
                    print(f", 索引日期")
                else:
                    print()
            else:
                print()
        except Exception as e:
            print(f"  - {symbol}: 读取失败 ({e})")
    
    if len(symbols) > 5:
        print(f"  ... 还有 {len(symbols) - 5} 个 symbols")

print("\n" + "=" * 70)
print("对比主数据库 (data/arctic_db)")
print("=" * 70)

main_arctic = Arctic("lmdb://./data/arctic_db")
main_libraries = main_arctic.list_libraries()

print(f"\n主数据库库数量: {len(main_libraries)}")
print(f"服务器数据库库数量: {len(libraries)}")

print(f"\n主数据库独有的库:")
for lib in main_libraries:
    if lib not in libraries:
        print(f"  - {lib}")

print(f"\n服务器数据库独有的库:")
for lib in libraries:
    if lib not in main_libraries:
        print(f"  - {lib}")

print("\n" + "=" * 70)
print("结论:")
print("=" * 70)

if set(libraries).issubset(set(main_libraries)):
    print("✓ 服务器数据库的所有库都存在于主数据库中")
    print("✓ 可以安全删除服务器数据库")
else:
    print("⚠ 服务器数据库有主数据库没有的库:")
    for lib in libraries:
        if lib not in main_libraries:
            print(f"  - {lib}")
    print("⚠ 需要手动确认这些库是否可以删除")

print("=" * 70)
