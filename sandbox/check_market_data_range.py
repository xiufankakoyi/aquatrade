#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 market_data 库的日期范围
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance
import polars as pl

arctic = get_arctic_instance()

print("检查 market_data 库的日期范围...")
print("=" * 70)

if "market_data" in arctic.list_libraries():
    lib = arctic["market_data"]
    symbols = lib.list_symbols()
    print(f"总共有 {len(symbols)} 只股票")
    
    # 随机采样10只股票检查日期范围
    import random
    sample_symbols = random.sample(symbols, min(10, len(symbols)))
    
    all_dates = []
    for symbol in sample_symbols:
        try:
            data = lib.read(symbol)
            if hasattr(data.data, 'to_pandas'):
                df = pl.from_pandas(data.data.to_pandas())
            else:
                df = pl.from_pandas(data.data) if not isinstance(data.data, pl.DataFrame) else data.data
            
            if 'trade_date' in df.columns:
                all_dates.extend([df['trade_date'].min(), df['trade_date'].max()])
                print(f"  {symbol}: {df['trade_date'].min()} ~ {df['trade_date'].max()} ({len(df)} 行)")
        except Exception as e:
            print(f"  {symbol}: 读取失败 ({e})")
    
    if all_dates:
        print(f"\n采样股票的日期范围:")
        print(f"  最早: {min(all_dates)}")
        print(f"  最晚: {max(all_dates)}")
    
    # 检查一只股票的完整数据
    if symbols:
        print(f"\n检查第一只股票 {symbols[0]} 的数据:")
        try:
            data = lib.read(symbols[0])
            if hasattr(data.data, 'to_pandas'):
                df = pl.from_pandas(data.data.to_pandas())
            else:
                df = pl.from_pandas(data.data) if not isinstance(data.data, pl.DataFrame) else data.data
            
            print(f"  行数: {len(df):,}")
            print(f"  列: {df.columns}")
            if 'trade_date' in df.columns:
                print(f"  日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
                # 显示日期分布
                date_counts = df.group_by('trade_date').agg(pl.len()).sort('trade_date')
                print(f"  日期数量: {len(date_counts)}")
        except Exception as e:
            print(f"  读取失败: {e}")
else:
    print("market_data 库不存在")
