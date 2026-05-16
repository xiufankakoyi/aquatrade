#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试 get_stock_daily_df() 函数"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
print(f"Arctic 实例: {arctic}")

libraries = arctic.list_libraries()
print(f"库列表: {libraries}")

if "stock_daily" in libraries:
    print("stock_daily 库存在")
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    print(f"  符号: {symbols}")
    if "stock_daily" in symbols:
        print("  stock_daily 符号存在")
        data = lib.read("stock_daily")
        df = data.data
        print(f"  数据类型: {type(df)}")
        if hasattr(df, 'to_pandas'):
            import polars as pl
            df = pl.from_arrow(df)
            print(f"  Polars DataFrame 形状: {df.shape}")
            print(f"  列名: {df.columns[:5]}")
    else:
        print("  stock_daily 符号不存在")
else:
    print("stock_daily 库不存在")
