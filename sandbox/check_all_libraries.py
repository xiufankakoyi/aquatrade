#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有 ArcticDB 库
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance
import polars as pl

arctic = get_arctic_instance()

print("检查所有 ArcticDB 库...")
print("=" * 70)

libraries = arctic.list_libraries()
print(f"总共有 {len(libraries)} 个库:")

for lib_name in libraries:
    print(f"\n{'='*70}")
    print(f"库: {lib_name}")
    print("=" * 70)
    
    lib = arctic[lib_name]
    symbols = lib.list_symbols()
    print(f"  Symbols ({len(symbols)} 个):")
    
    for symbol in symbols[:10]:  # 只显示前10个
        try:
            data = lib.read(symbol)
            if hasattr(data.data, 'to_pandas'):
                df = pl.from_pandas(data.data.to_pandas())
            else:
                df = pl.from_pandas(data.data) if not isinstance(data.data, pl.DataFrame) else data.data
            
            print(f"    - {symbol}: {len(df):,} 行", end="")
            
            if 'trade_date' in df.columns:
                print(f", 日期: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
            else:
                print()
        except Exception as e:
            print(f"    - {symbol}: 读取失败 ({e})")
    
    if len(symbols) > 10:
        print(f"    ... 还有 {len(symbols) - 10} 个 symbols")
