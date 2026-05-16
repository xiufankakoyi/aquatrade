#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 market_data 库的数据结构
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance
import polars as pl

arctic = get_arctic_instance()

print("检查 market_data 库的数据结构...")
print("=" * 70)

if "market_data" in arctic.list_libraries():
    lib = arctic["market_data"]
    symbols = lib.list_symbols()
    print(f"总共有 {len(symbols)} 只股票\n")
    
    # 检查第一只股票
    if symbols:
        symbol = symbols[0]
        print(f"检查股票 {symbol}:")
        try:
            data = lib.read(symbol)
            if hasattr(data.data, 'to_pandas'):
                df = pl.from_pandas(data.data.to_pandas())
            else:
                df = pl.from_pandas(data.data) if not isinstance(data.data, pl.DataFrame) else data.data
            
            print(f"  行数: {len(df):,}")
            print(f"  列: {list(df.columns)}")
            print(f"\n  前5行:")
            print(df.head().to_pandas().to_string())
            
            # 检查索引
            if hasattr(data.data, 'index'):
                print(f"\n  Pandas索引: {data.data.index}")
                
        except Exception as e:
            import traceback
            print(f"  读取失败: {e}")
            traceback.print_exc()
