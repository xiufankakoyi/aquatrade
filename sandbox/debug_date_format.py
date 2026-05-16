#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def debug_date_format():
    """调试日期格式"""
    try:
        arctic = get_arctic_instance_for_library("stock_daily")
        lib = arctic["stock_daily"]
        symbols = lib.list_symbols()
        
        # 读取第一只股票的数据
        first_symbol = symbols[0]
        print(f"读取股票: {first_symbol}")
        
        data = lib.read(first_symbol)
        raw_data = data.data
        
        if hasattr(raw_data, 'to_pandas') and not hasattr(raw_data, 'empty'):
            df = pl.from_arrow(raw_data)
        elif hasattr(raw_data, 'empty'):
            df = pl.from_pandas(raw_data)
        elif hasattr(raw_data, 'is_empty'):
            df = raw_data
        
        print(f"数据形状: {df.shape}")
        print(f"数据列: {df.columns}")
        
        if 'trade_date' in df.columns:
            print(f"\ntrade_date 列数据类型: {df['trade_date'].dtype}")
            print(f"前5个日期值:")
            dates = df.select('trade_date').to_series().to_list()
            for d in dates[:5]:
                print(f"  值: {d!r}, 类型: {type(d)}, str: {str(d)}")
        
        # 测试过滤
        target_date = "2025-11-20"
        print(f"\n测试过滤日期: {target_date}")
        filtered = df.filter(pl.col('trade_date') == target_date)
        print(f"过滤结果行数: {filtered.shape[0]}")
        
        # 尝试不同格式
        print("\n尝试不同日期格式:")
        test_dates = ["2025-11-20", "2025-11-19", "2025-11-18"]
        for test_date in test_dates:
            filtered = df.filter(pl.col('trade_date') == test_date)
            print(f"  {test_date}: {filtered.shape[0]} 行")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_date_format()
