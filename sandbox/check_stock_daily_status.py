#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def check_stock_daily():
    """检查 stock_daily 库的当前状态"""
    arctic = get_arctic_instance_for_library("stock_daily")
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    
    print(f"stock_daily 库符号数量: {len(symbols)}")
    
    # 统计总行数
    total_rows = 0
    date_set = set()
    
    for i, symbol in enumerate(symbols[:100]):  # 只检查前100只
        try:
            data = lib.read(symbol)
            df = pl.from_arrow(data.data)
            total_rows += len(df)
            
            if 'trade_date_basic' in df.columns:
                dates = df['trade_date_basic'].unique().to_list()
                date_set.update(dates)
        except Exception as e:
            print(f"Error reading {symbol}: {e}")
    
    print(f"前100只股票总行数: {total_rows}")
    print(f"日期数量: {len(date_set)}")
    print(f"日期: {sorted(date_set)[:10]}")

if __name__ == '__main__':
    check_stock_daily()
