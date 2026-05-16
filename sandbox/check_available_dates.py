#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def check_available_dates():
    """检查数据库中实际有哪些日期"""
    arctic = get_arctic_instance_for_library("stock_daily")
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    
    print(f"总股票数: {len(symbols)}")
    
    # 收集所有日期
    all_dates = set()
    
    for i, symbol in enumerate(symbols[:100]):  # 只检查前100只
        try:
            data = lib.read(symbol)
            df = pl.from_arrow(data.data)
            
            if 'trade_date_basic' in df.columns:
                dates = df['trade_date_basic'].unique().to_list()
                all_dates.update(dates)
        except:
            pass
    
    print(f"\n前100只股票中的唯一日期 ({len(all_dates)} 个):")
    sorted_dates = sorted(all_dates)
    print(f"最早: {sorted_dates[0] if sorted_dates else 'N/A'}")
    print(f"最晚: {sorted_dates[-1] if sorted_dates else 'N/A'}")
    print(f"\n所有日期: {sorted_dates}")

if __name__ == '__main__':
    check_available_dates()
