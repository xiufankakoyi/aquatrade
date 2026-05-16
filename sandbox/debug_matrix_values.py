"""
测试 build_from_single_dataframe 中的矩阵值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import numpy as np
import pandas as pd
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.backtest.factor_matrix import FactorMatrixBuilder, stock_codes_to_int_vectorized_polars

# 创建数据管理器
data_manager = UnifiedDataManager()

# 创建回测引擎
config = BacktestConfig()
engine = UnifiedBacktestEngine(data_query=data_manager, config=config)

# 读取数据
df = data_manager.read('stock_daily', start_date='2024-01-02', end_date='2024-01-10')

# 测试 _compute_status_fields
df_enhanced = engine._compute_status_fields(df)

# 模拟 build_from_single_dataframe 的逻辑
trading_dates = df_enhanced['trade_date'].unique().sort().to_list()
trading_dates = [str(d) for d in trading_dates]

stock_codes = df_enhanced['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()

T = len(trading_dates)
N = len(stock_codes)

date_to_idx = {date: i for i, date in enumerate(trading_dates)}
codes_int = stock_codes_to_int_vectorized_polars(pl.Series(stock_codes))
code_to_idx = {str(c): i for i, c in enumerate(codes_int)}

builder = FactorMatrixBuilder()
F = len(builder.factor_names)

values = np.full((T, N, F), np.nan, dtype=np.float32)

available_factors = [c for c in builder.factor_names if c in df_enhanced.columns]

print(f"available_factors: {available_factors}")

df_with_idx = df_enhanced.select(['trade_date', 'stock_code'] + available_factors).with_columns([
    pl.col('trade_date').cast(pl.Utf8).replace_strict(date_to_idx, default=None).alias('date_idx'),
    pl.col('stock_code').cast(pl.Utf8).str.strip_chars().replace_strict(
        code_to_idx, default=None
    ).alias('code_idx')
])

df_with_idx = df_with_idx.filter(
    pl.col('date_idx').is_not_null() & pl.col('code_idx').is_not_null()
)

print(f"\ndf_with_idx 行数: {len(df_with_idx)}")

# 获取索引
t_indices = df_with_idx['date_idx'].to_numpy().astype(np.int32)
n_indices = df_with_idx['code_idx'].to_numpy().astype(np.int32)

print(f"\n索引统计:")
print(f"  t_indices 范围: {t_indices.min()} - {t_indices.max()}")
print(f"  n_indices 范围: {n_indices.min()} - {n_indices.max()}")

# 填充矩阵
for f_idx, factor_name in enumerate(available_factors):
    if factor_name not in ['is_limit_up', 'is_suspended']:
        continue
    
    vals = df_with_idx[factor_name].to_numpy()
    print(f"\n{factor_name}:")
    print(f"  vals 类型: {vals.dtype}")
    print(f"  vals 形状: {vals.shape}")
    print(f"  vals 唯一值 (前10): {np.unique(vals)[:10]}")
    
    mask = ~np.isnan(vals)
    print(f"  mask True 数量: {mask.sum()}")
    
    if mask.any():
        values[t_indices[mask], n_indices[mask], f_idx] = vals[mask]
        
        # 检查填充后的值
        filled_vals = values[:, :, f_idx]
        print(f"  填充后唯一值 (前10): {np.unique(filled_vals[~np.isnan(filled_vals)])[:10]}")

# 检查第2天 (2024-01-03) 的数据
date_str = '2024-01-03'
date_idx = date_to_idx.get(date_str, -1)
print(f"\n日期 {date_str} 的索引: {date_idx}")

if date_idx >= 0:
    factor_slice = values[date_idx, :, :]
    
    is_limit_up_idx = available_factors.index('is_limit_up') if 'is_limit_up' in available_factors else -1
    is_suspended_idx = available_factors.index('is_suspended') if 'is_suspended' in available_factors else -1
    
    if is_limit_up_idx >= 0:
        limit_up_col = factor_slice[:, is_limit_up_idx]
        print(f"\nis_limit_up 值统计:")
        print(f"  唯一值: {np.unique(limit_up_col[~np.isnan(limit_up_col)])}")
        print(f"  True (1.0): {(limit_up_col == 1.0).sum()}")
        print(f"  False (0.0): {(limit_up_col == 0.0).sum()}")
    
    if is_suspended_idx >= 0:
        suspended_col = factor_slice[:, is_suspended_idx]
        print(f"\nis_suspended 值统计:")
        print(f"  唯一值: {np.unique(suspended_col[~np.isnan(suspended_col)])}")
        print(f"  True (1.0): {(suspended_col == 1.0).sum()}")
        print(f"  False (0.0): {(suspended_col == 0.0).sum()}")
