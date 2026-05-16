"""
调试 df_with_idx 中的列
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
print("调试 df_with_idx 中的列")
print("=" * 80)

# 获取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

stock_daily = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"\n原始数据:")
print(f"  列数: {len(stock_daily.columns)}")

# 模拟 _compute_status_fields 方法
df_enhanced = stock_daily

# 计算 is_limit_up
if 'limit_up' in df_enhanced.columns and 'close' in df_enhanced.columns:
    df_enhanced = df_enhanced.with_columns([
        (pl.col('close') >= pl.col('limit_up')).cast(pl.Float64).alias('is_limit_up')
    ])

print(f"\n计算后数据:")
print(f"  列数: {len(df_enhanced.columns)}")
print(f"  is_limit_up 唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")

# 模拟 FactorMatrixBuilder.build_from_single_dataframe 方法
trading_dates = df_enhanced['trade_date'].unique().sort().to_list()
trading_dates = [str(d) for d in trading_dates]

stock_codes = df_enhanced['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()

T = len(trading_dates)
N = len(stock_codes)

date_to_idx = {date: i for i, date in enumerate(trading_dates)}

# 检查 df_enhanced 中是否有 is_limit_up 列
print(f"\n检查 df_enhanced 中的 is_limit_up 列:")
print(f"  'is_limit_up' in df_enhanced.columns: {'is_limit_up' in df_enhanced.columns}")
print(f"  is_limit_up 唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")

# 模拟 available_factors
factor_names = [
    'open', 'high', 'low', 'close', 'volume', 'amount',
    'total_mv', 'float_mv', 'turnover_rate', 'volume_ratio',
    'ma5', 'ma10', 'ma20', 'volume_ma5',
    'is_st', 'is_kc', 'is_cy',
    'is_limit_up', 'is_limit_down', 'is_suspended',
    'adj_factor', 'prev_close', 'days_listed'
]

available_factors = [c for c in factor_names if c in df_enhanced.columns]

print(f"\navailable_factors 数量: {len(available_factors)}")
print(f"  is_limit_up in available_factors: {'is_limit_up' in available_factors}")

# 模拟 df_with_idx
df_with_idx = df_enhanced.select(['trade_date', 'stock_code'] + available_factors)

print(f"\ndf_with_idx 列数: {len(df_with_idx.columns)}")
print(f"  'is_limit_up' in df_with_idx.columns: {'is_limit_up' in df_with_idx.columns}")

# 检查 df_with_idx 中的 is_limit_up 列
if 'is_limit_up' in df_with_idx.columns:
    print(f"  is_limit_up 唯一值: {df_with_idx['is_limit_up'].unique().to_list()}")
    print(f"  is_limit_up 前10行: {df_with_idx['is_limit_up'].head(10).to_list()}")
