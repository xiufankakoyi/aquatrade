"""
调试 _compute_status_fields 方法
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager

# 创建数据管理器
data_manager = UnifiedDataManager()

print("=" * 80)
print("调试 _compute_status_fields 方法")
print("=" * 80)

# 获取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

stock_daily = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"\n原始数据:")
print(f"  列数: {len(stock_daily.columns)}")
print(f"  行数: {len(stock_daily)}")

# 检查 is_limit_up 列
if 'is_limit_up' in stock_daily.columns:
    print(f"\n原始 is_limit_up 列:")
    print(f"  唯一值数量: {stock_daily['is_limit_up'].n_unique()}")
    print(f"  最小值: {stock_daily['is_limit_up'].min()}")
    print(f"  最大值: {stock_daily['is_limit_up'].max()}")

# 模拟 _compute_status_fields 方法
df_enhanced = stock_daily

# 计算 is_limit_up
if 'limit_up' in df_enhanced.columns and 'close' in df_enhanced.columns:
    df_enhanced = df_enhanced.with_columns([
        (pl.col('close') >= pl.col('limit_up')).cast(pl.Float64).alias('is_limit_up')
    ])
else:
    df_enhanced = df_enhanced.with_columns([
        pl.lit(0.0).cast(pl.Float64).alias('is_limit_up')
    ])

print(f"\n计算后数据:")
print(f"  列数: {len(df_enhanced.columns)}")

# 检查计算后的 is_limit_up
print(f"\n计算后 is_limit_up 列:")
print(f"  唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")
print(f"  最小值: {df_enhanced['is_limit_up'].min()}")
print(f"  最大值: {df_enhanced['is_limit_up'].max()}")

# 检查是否有重复的列
print(f"\n检查重复列:")
is_limit_up_count = 0
for col in df_enhanced.columns:
    if col == 'is_limit_up':
        is_limit_up_count += 1
print(f"  is_limit_up 列数量: {is_limit_up_count}")

# 检查 is_limit_up 列的值
print(f"\nis_limit_up 列的值:")
print(f"  前10行: {df_enhanced['is_limit_up'].head(10).to_list()}")
