#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查所有库的数据"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
print("ArcticDB 库详情:")
for lib_name in arctic.list_libraries():
    lib = arctic[lib_name]
    symbols = lib.list_symbols()
    print(f"\n{lib_name} 库:")
    print(f"  符号数量: {len(symbols)}")
    if symbols:
        print(f"  符号: {symbols[:3]}...")  # 只显示前3个
