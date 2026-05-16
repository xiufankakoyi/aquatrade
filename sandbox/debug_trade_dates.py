#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试脚本：检查 ArcticDB 独立目录模式中的 stock_daily
"""
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

def debug_stock_daily_independent():
    """调试独立目录模式中的 stock_daily"""
    try:
        # 使用独立库实例（Windows 平台推荐）
        print("=" * 60)
        print("使用独立库实例模式获取 stock_daily...")
        arctic = get_arctic_instance_for_library("stock_daily")
        
        if arctic is None:
            print("❌ 无法获取 Arctic 实例")
            return
        
        print(f"✓ 获取到 Arctic 实例")
        print(f"库列表: {arctic.list_libraries()}")
        print()
        
        if "stock_daily" not in arctic.list_libraries():
            print("❌ stock_daily 库不存在!")
            return
        
        lib = arctic["stock_daily"]
        print("=" * 60)
        print("stock_daily 库中的符号:")
        print(lib.list_symbols())
        print()
        
        if "stock_daily" not in lib.list_symbols():
            print("❌ stock_daily 符号不存在!")
            return
        
        print("=" * 60)
        print("读取数据...")
        data = lib.read("stock_daily")
        raw_data = data.data
        
        print(f"数据类型: {type(raw_data)}")
        print()
        
        # 转换为 Polars DataFrame
        if hasattr(raw_data, 'to_pandas') and not hasattr(raw_data, 'empty'):
            df = pl.from_arrow(raw_data)
            print("✓ 从 PyArrow Table 转换为 Polars")
        elif hasattr(raw_data, 'empty'):
            df = pl.from_pandas(raw_data)
            print("✓ 从 pandas DataFrame 转换为 Polars")
        elif hasattr(raw_data, 'is_empty'):
            df = raw_data
            print("✓ 已经是 Polars DataFrame")
        else:
            df = pl.DataFrame(raw_data)
            print("✓ 从其他类型转换为 Polars")
        
        print()
        print("=" * 60)
        print(f"数据形状: {df.shape}")
        print(f"数据列: {df.columns}")
        print()
        
        # 检查日期列
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        print(f"可能的日期列: {date_cols}")
        print()
        
        if 'trade_date' in df.columns:
            print("=" * 60)
            print("trade_date 列信息:")
            print(f"数据类型: {df['trade_date'].dtype}")
            print(f"唯一值数量: {df['trade_date'].n_unique()}")
            print()
            print("前10个日期:")
            dates = df.select('trade_date').unique().to_series().to_list()
            print(dates[:10])
            print()
            print("转换为字符串后的前10个:")
            str_dates = [str(d) for d in dates[:10]]
            print(str_dates)
        else:
            print("❌ 没有找到 'trade_date' 列!")
            print("\n前5行数据预览:")
            print(df.head())
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_stock_daily_independent()
