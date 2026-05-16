#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试筛选器 API
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
from data_svc.storage.arcticdb_manager import get_arctic_instance

def get_stock_daily_df():
    """从 ArcticDB 获取股票日线数据"""
    try:
        arctic = get_arctic_instance()
        
        if "stock_daily" in arctic.list_libraries():
            lib = arctic["stock_daily"]
            if "stock_daily" in lib.list_symbols():
                data = lib.read("stock_daily")
                df = data.data
                
                # 如果是 PyArrow Table，转换为 Polars DataFrame
                if hasattr(df, 'to_pandas'):
                    df = pl.from_arrow(df)
                elif isinstance(df, pd.DataFrame):
                    df = pl.from_pandas(df)
                    
                return df
    except Exception as e:
        print(f"Error: {e}")
    return None

print("=" * 70)
print("调试筛选器")
print("=" * 70)

df = get_stock_daily_df()
print(f"\n1. 获取数据")
print(f"   类型: {type(df)}")
print(f"   是否为空: {df.is_empty() if df is not None else 'None'}")

if df is not None:
    print(f"   列: {df.columns}")
    print(f"   行数: {len(df)}")
    
    # 检查日期
    print(f"\n2. 日期范围")
    try:
        dates = df.select(pl.col('trade_date')).to_series().to_list()
        unique_dates = sorted(set(dates))
        print(f"   唯一日期数: {len(unique_dates)}")
        print(f"   最近5个日期: {unique_dates[-5:]}")
    except Exception as e:
        print(f"   错误: {e}")
    
    # 测试过滤
    print(f"\n3. 测试过滤")
    try:
        date = '2026-02-13'
        date_obj = pd.to_datetime(date).date()
        filtered = df.filter(pl.col('trade_date') == date_obj)
        print(f"   过滤后行数: {len(filtered)}")
        print(f"   是否为空: {filtered.is_empty()}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
