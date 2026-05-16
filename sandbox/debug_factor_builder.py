"""
调试 FactorMatrixBuilder.build_from_single_dataframe 方法
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.factor_matrix import FactorMatrixBuilder

# 创建数据管理器
data_manager = UnifiedDataManager()

print("=" * 80)
print("调试 FactorMatrixBuilder.build_from_single_dataframe")
print("=" * 80)

# 获取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

stock_daily = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"\n原始数据:")
print(f"  列数: {len(stock_daily.columns)}")
print(f"  行数: {len(stock_daily)}")

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

print(f"\n计算后数据:")
print(f"  列数: {len(df_enhanced.columns)}")

# 检查计算后的 is_limit_up
print(f"\n计算后 is_limit_up 列:")
print(f"  唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")

# 构建 FactorMatrix
builder = FactorMatrixBuilder()
factor_matrix = builder.build_from_single_dataframe(df_enhanced, use_cache=False)

print(f"\nFactorMatrix 信息:")
print(f"  形状: {factor_matrix.values.shape}")
print(f"  日期数: {len(factor_matrix.dates)}")
print(f"  股票代码数: {len(factor_matrix.codes_str)}")
print(f"  因子名称: {factor_matrix.factor_names}")

# 检查 is_limit_up 字段
if 'is_limit_up' in factor_matrix.factor_names:
    is_limit_up_idx = factor_matrix.factor_names.index('is_limit_up')
    is_limit_up_matrix = factor_matrix.values[:, :, is_limit_up_idx]
    
    print(f"\nis_limit_up 矩阵:")
    print(f"  形状: {is_limit_up_matrix.shape}")
    print(f"  类型: {is_limit_up_matrix.dtype}")
    print(f"  最小值: {np.nanmin(is_limit_up_matrix)}")
    print(f"  最大值: {np.nanmax(is_limit_up_matrix)}")
    print(f"  唯一值数量: {len(np.unique(is_limit_up_matrix[~np.isnan(is_limit_up_matrix)]))}")
