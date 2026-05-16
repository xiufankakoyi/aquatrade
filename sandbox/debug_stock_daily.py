#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试 stock_daily 数据结构
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

print("检查 stock_daily 库结构...")
print("=" * 70)

if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    if "stock_daily" in lib.list_symbols():
        data = lib.read("stock_daily")
        df = data.data
        
        print(f"数据形状: {df.shape}")
        print(f"\n列名:")
        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. {col}")
        
        print(f"\n前5行:")
        print(df.head())
        
        print(f"\n数据类型:")
        print(df.dtypes)
        
        print(f"\ntrade_date 列示例:")
        if 'trade_date' in df.columns:
            print(df['trade_date'].head(10))
        else:
            print("trade_date 列不存在！")
            # 检查是否有日期相关的列
            date_cols = [col for col in df.columns if 'date' in col.lower()]
            print(f"可能的日期列: {date_cols}")
    else:
        print("stock_daily symbol 不存在")
else:
    print("stock_daily 库不存在")
