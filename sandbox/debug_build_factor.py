"""
调试 _build_factor_matrix_from_df 方法
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
print("调试 _build_factor_matrix_from_df")
print("=" * 80)

# 获取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

stock_daily = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"\n原始数据:")
print(f"  列: {stock_daily.columns}")
print(f"  行数: {len(stock_daily)}")

# 检查 is_limit_up 列
if 'is_limit_up' in stock_daily.columns:
    print(f"\nis_limit_up 列:")
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

# 计算 is_limit_down
if 'limit_down' in df_enhanced.columns and 'close' in df_enhanced.columns:
    df_enhanced = df_enhanced.with_columns([
        (pl.col('close') <= pl.col('limit_down')).cast(pl.Float64).alias('is_limit_down')
    ])
else:
    df_enhanced = df_enhanced.with_columns([
        pl.lit(0.0).cast(pl.Float64).alias('is_limit_down')
    ])

# 计算 is_suspended
if 'volume' in df_enhanced.columns and 'close' in df_enhanced.columns:
    df_enhanced = df_enhanced.with_columns([
        ((pl.col('volume') == 0) | (pl.col('close') == 0)).cast(pl.Float64).alias('is_suspended')
    ])
else:
    df_enhanced = df_enhanced.with_columns([
        pl.lit(0.0).cast(pl.Float64).alias('is_suspended')
    ])

print(f"\n计算后的数据:")
print(f"  列: {df_enhanced.columns}")

# 检查计算后的 is_limit_up
print(f"\n计算后的 is_limit_up:")
print(f"  唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")
print(f"  True (1.0): {(df_enhanced['is_limit_up'] == 1.0).sum()}")
print(f"  False (0.0): {(df_enhanced['is_limit_up'] == 0.0).sum()}")

# 检查计算后的 is_suspended
print(f"\n计算后的 is_suspended:")
print(f"  唯一值: {df_enhanced['is_suspended'].unique().to_list()}")
print(f"  True (1.0): {(df_enhanced['is_suspended'] == 1.0).sum()}")
print(f"  False (0.0): {(df_enhanced['is_suspended'] == 0.0).sum()}")
