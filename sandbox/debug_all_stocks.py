#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from server.routes.screener_routes import get_all_stocks_daily_df

def debug_all_stocks():
    """调试获取所有股票数据"""
    try:
        print("正在获取 2025-11-20 的所有股票数据...")
        df = get_all_stocks_daily_df(target_date="2025-11-20")
        
        if df is None:
            print("❌ 返回 None")
            return
            
        if df.is_empty():
            print("❌ 返回空 DataFrame")
            return
        
        print(f"✓ 成功获取数据")
        print(f"数据形状: {df.shape}")
        print(f"数据列: {df.columns}")
        print(f"\n前5行:")
        print(df.head())
        
        # 统计股票数量
        if 'stock_code' in df.columns:
            stock_count = df.select('stock_code').n_unique()
            print(f"\n股票数量: {stock_count}")
        elif 'ts_code' in df.columns:
            stock_count = df.select('ts_code').n_unique()
            print(f"\n股票数量 (ts_code): {stock_count}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_all_stocks()
