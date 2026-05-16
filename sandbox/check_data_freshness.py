#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据新鲜度
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

print(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")
print()

# 检查 stock_daily 库
if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    data = lib.read("stock_daily")
    df = data.data
    
    pdf_reset = df.reset_index()
    latest_date = pdf_reset['trade_date'].max()
    earliest_date = pdf_reset['trade_date'].min()
    
    print(f"stock_daily 数据:")
    print(f"  最早日期: {earliest_date}")
    print(f"  最新日期: {latest_date}")
    print(f"  数据天数: {pdf_reset['trade_date'].nunique()}")
    print(f"  总记录数: {len(df)}")
else:
    print("stock_daily 库不存在")

# 检查 market_data 库（实时数据）
print()
if "market_data" in arctic.list_libraries():
    lib = arctic["market_data"]
    symbols = list(lib.list_symbols())
    
    # 读取一个示例股票查看最新日期
    if symbols:
        data = lib.read(symbols[0])
        df = data.data
        if df is not None and not df.empty:
            latest_date = df.index.max()
            print(f"market_data 数据:")
            print(f"  股票数量: {len(symbols)}")
            print(f"  示例股票 {symbols[0]} 最新日期: {latest_date}")
else:
    print("market_data 库不存在")
