"""
调试原始数据中的 is_suspended 和 is_limit_up 值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
import numpy as np
from data_svc.unified_data_manager import UnifiedDataManager

# 创建数据管理器
data_manager = UnifiedDataManager()

# 读取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

df = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"数据形状: {df.shape}")
print(f"数据列: {df.columns}")

# 检查 is_suspended 列
if 'is_suspended' in df.columns:
    print(f"\nis_suspended 列统计:")
    print(f"  唯一值: {df['is_suspended'].unique().to_list()}")
    print(f"  类型: {df['is_suspended'].dtype}")
    
    # 检查一些具体值
    print(f"\n  前10个非空值:")
    non_null = df.filter(pl.col('is_suspended').is_not_null())
    for row in non_null.head(10).iter_rows(named=True):
        print(f"    {row['stock_code']} @ {row['trade_date']}: is_suspended={row['is_suspended']}")

# 检查 is_limit_up 列
if 'is_limit_up' in df.columns:
    print(f"\nis_limit_up 列统计:")
    print(f"  唯一值: {df['is_limit_up'].unique().to_list()}")
    print(f"  类型: {df['is_limit_up'].dtype}")
    
    # 检查一些具体值
    print(f"\n  前10个非空值:")
    non_null = df.filter(pl.col('is_limit_up').is_not_null())
    for row in non_null.head(10).iter_rows(named=True):
        print(f"    {row['stock_code']} @ {row['trade_date']}: is_limit_up={row['is_limit_up']}")

# 检查 open 列
if 'open' in df.columns:
    print(f"\nopen 列统计:")
    print(f"  类型: {df['open'].dtype}")
    print(f"  NaN: {df['open'].is_null().sum()}")
    print(f"  0: {(df['open'] == 0).sum()}")
    print(f"  >0: {(df['open'] > 0).sum()}")
