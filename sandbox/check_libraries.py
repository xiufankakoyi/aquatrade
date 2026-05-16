#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def check_libraries():
    """检查 stock_daily 和 stock_basic 库的内容"""
    
    # 检查 stock_daily
    print("=" * 60)
    print("stock_daily 库")
    print("=" * 60)
    try:
        arctic_daily = get_arctic_instance_for_library("stock_daily")
        lib_daily = arctic_daily["stock_daily"]
        symbols_daily = lib_daily.list_symbols()
        print(f"符号数量: {len(symbols_daily)}")
        
        if symbols_daily:
            # 读取第一个符号
            symbol = symbols_daily[0]
            data = lib_daily.read(symbol)
            df = pl.from_arrow(data.data)
            print(f"\n第一个符号: {symbol}")
            print(f"行数: {len(df)}")
            print(f"列: {df.columns}")
            
            if 'trade_date_basic' in df.columns:
                dates = df['trade_date_basic'].unique().to_list()
                print(f"日期范围: {sorted(dates)[:3]} ... {sorted(dates)[-3:]}")
    except Exception as e:
        print(f"错误: {e}")
    
    # 检查 stock_basic
    print("\n" + "=" * 60)
    print("stock_basic 库")
    print("=" * 60)
    try:
        arctic_basic = get_arctic_instance_for_library("stock_basic")
        lib_basic = arctic_basic["stock_basic"]
        symbols_basic = lib_basic.list_symbols()
        print(f"符号数量: {len(symbols_basic)}")
        print(f"符号列表: {symbols_basic[:10]}")
        
        if symbols_basic:
            # 检查是否有 stock_daily 符号
            if "stock_daily" in symbols_basic:
                data = lib_basic.read("stock_daily")
                df = pl.from_arrow(data.data)
                print(f"\nstock_basic 中的 stock_daily 符号:")
                print(f"行数: {len(df)}")
                print(f"列: {df.columns}")
                
                if 'trade_date' in df.columns:
                    dates = df['trade_date'].unique().to_list()
                    print(f"日期数量: {len(dates)}")
                    print(f"日期范围: {sorted(dates)[:3]} ... {sorted(dates)[-3:]}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    check_libraries()
