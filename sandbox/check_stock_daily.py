#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 stock_daily 库中的数据"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic["stock_daily"]
print("stock_daily 库信息:")
symbols = lib.list_symbols()
print(f"  符号数量: {len(symbols)}")
if symbols:
    for symbol in symbols:
        print(f"  - {symbol}")
        try:
            data = lib.read(symbol)
            df = data.data
            print(f"    数据类型: {type(df)}")
            if hasattr(df, 'shape'):
                print(f"    数据形状: {df.shape}")
            if hasattr(df, 'head'):
                print(f"    前几行:")
                print(df.head())
        except Exception as e:
            print(f"    读取错误: {e}")
