#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def test_date_filter():
    """测试日期过滤"""
    arctic = get_arctic_instance_for_library("stock_daily")
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    
    print(f"总股票数: {len(symbols)}")
    
    target_date = '2025-11-20'
    normalized_date = target_date.replace('-', '')
    print(f"目标日期: {target_date}")
    print(f"标准化日期: {normalized_date}")
    
    # 读取前10只股票测试
    test_count = 0
    for symbol in symbols[:10]:
        data = lib.read(symbol)
        df = pl.from_arrow(data.data)
        
        print(f"\n{symbol}:")
        print(f"  总行数: {len(df)}")
        
        if 'trade_date_basic' in df.columns:
            unique_dates = df['trade_date_basic'].unique().to_list()
            print(f"  trade_date_basic 唯一值: {unique_dates[:5]}")
            
            # 测试过滤
            filtered = df.filter(pl.col('trade_date_basic') == normalized_date)
            print(f"  过滤后行数: {len(filtered)}")
            
            if len(filtered) > 0:
                test_count += 1
    
    print(f"\n有 {target_date} 数据的股票数: {test_count}")

if __name__ == '__main__':
    test_date_filter()
