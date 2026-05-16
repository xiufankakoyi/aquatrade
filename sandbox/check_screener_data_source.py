#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查股票筛选器使用的数据源
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

print("检查 stock_daily 库...")
print("=" * 50)

if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    symbols = list(lib.list_symbols())
    print(f"库存在，表数量: {len(symbols)}")
    
    for symbol in symbols:
        try:
            data = lib.read(symbol)
            df = data.data
            print(f"\n表: {symbol}")
            print(f"  行数: {len(df)}")
            print(f"  列名: {list(df.columns)}")
            
            # 检查 trade_date 列
            if 'trade_date' in df.columns:
                print(f"  trade_date 类型: {df['trade_date'].dtype}")
                print(f"  最新日期: {df['trade_date'].max()}")
            elif hasattr(df.index, 'names'):
                print(f"  索引: {df.index.names}")
                if 'trade_date' in df.index.names:
                    print(f"  索引最新日期: {df.index.get_level_values('trade_date').max()}")
        except Exception as e:
            print(f"  读取错误: {e}")
else:
    print("stock_daily 库不存在！")

print("\n" + "=" * 50)
print("检查 daily 库...")

if "daily" in arctic.list_libraries():
    lib = arctic["daily"]
    symbols = list(lib.list_symbols())
    print(f"库存在，表数量: {len(symbols)}")
    if symbols:
        print(f"  示例表: {symbols[:5]}")
else:
    print("daily 库不存在！")
