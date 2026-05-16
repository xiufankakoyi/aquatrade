#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 factor 库的数据
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

print("检查 factor 库...")
print("=" * 60)

if "factor" in arctic.list_libraries():
    lib = arctic["factor"]
    symbols = list(lib.list_symbols())
    print(f"库存在，表数量: {len(symbols)}")
    
    for symbol in symbols:
        try:
            data = lib.read(symbol)
            df = data.data
            print(f"\n表: {symbol}")
            print(f"  行数: {len(df)}")
            print(f"  列名: {list(df.columns)[:20]}")  # 只显示前20个列名
            if len(df.columns) > 20:
                print(f"  ... 还有 {len(df.columns) - 20} 个列")
        except Exception as e:
            print(f"  读取错误: {e}")
else:
    print("factor 库不存在！")
