#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中的数据范围
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance
import polars as pl

arctic = get_arctic_instance()

print("检查数据库中的数据范围...")
print("=" * 70)

if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    if "stock_daily" in lib.list_symbols():
        data = lib.read("stock_daily")
        
        # 转换为 Polars
        if hasattr(data.data, 'to_pandas'):
            df = pl.from_pandas(data.data.to_pandas())
        else:
            df = pl.from_pandas(data.data) if not isinstance(data.data, pl.DataFrame) else data.data
        
        print(f"总记录数: {len(df):,}")
        print(f"列数: {len(df.columns)}")
        
        if 'trade_date' in df.columns:
            print(f"\n日期范围:")
            print(f"  最早: {df['trade_date'].min()}")
            print(f"  最晚: {df['trade_date'].max()}")
            print(f"  唯一日期数: {df['trade_date'].n_unique()}")
        
        if 'stock_code' in df.columns:
            print(f"\n股票数量: {df['stock_code'].n_unique()}")
        elif 'ts_code' in df.columns:
            print(f"\n股票数量: {df['ts_code'].n_unique()}")
        
        # 显示按日期分布
        if 'trade_date' in df.columns:
            print(f"\n日期分布 (前10天):")
            date_counts = df.group_by('trade_date').agg(pl.count()).sort('trade_date')
            for row in date_counts.head(10).to_dicts():
                print(f"  {row['trade_date']}: {row['count']:,} 条")
            
            print(f"\n日期分布 (后10天):")
            for row in date_counts.tail(10).to_dicts():
                print(f"  {row['trade_date']}: {row['count']:,} 条")
    else:
        print("stock_daily symbol 不存在")
else:
    print("stock_daily 库不存在")
