"""
测试 build_from_single_dataframe 方法
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import numpy as np
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.backtest.factor_matrix import FactorMatrixBuilder

# 创建数据管理器
data_manager = UnifiedDataManager()

# 创建回测引擎
config = BacktestConfig()
engine = UnifiedBacktestEngine(data_query=data_manager, config=config)

# 读取数据
df = data_manager.read('stock_daily', start_date='2024-01-02', end_date='2024-01-10')

print(f"原始数据列: {df.columns}")

# 测试 _compute_status_fields
df_enhanced = engine._compute_status_fields(df)

print(f"\n增强后数据列: {df_enhanced.columns}")

# 检查 is_limit_up 和 is_suspended 是否在列中
print(f"\nis_limit_up 在列中: {'is_limit_up' in df_enhanced.columns}")
print(f"is_suspended 在列中: {'is_suspended' in df_enhanced.columns}")

# 使用 FactorMatrixBuilder 构建矩阵
builder = FactorMatrixBuilder()

print(f"\nFactorMatrixBuilder factor_names: {builder.factor_names}")

# 检查 available_factors
available_factors = [c for c in builder.factor_names if c in df_enhanced.columns]
print(f"\navailable_factors: {available_factors}")

# 构建矩阵
fm = builder.build_from_single_dataframe(df_enhanced, use_cache=False)

print(f"\n因子矩阵信息:")
print(f"  形状: {fm.values.shape}")
print(f"  因子名称: {fm.factor_names}")

# 检查 is_limit_up 和 is_suspended 的索引
is_limit_up_idx = fm.factor_names.index('is_limit_up') if 'is_limit_up' in fm.factor_names else -1
is_suspended_idx = fm.factor_names.index('is_suspended') if 'is_suspended' in fm.factor_names else -1

print(f"\n因子索引:")
print(f"  is_limit_up: {is_limit_up_idx}")
print(f"  is_suspended: {is_suspended_idx}")

# 检查第2天 (2024-01-03) 的数据
date_str = '2024-01-03'
date_idx = fm.date_to_idx.get(date_str, -1)
print(f"\n日期 {date_str} 的索引: {date_idx}")

if date_idx >= 0:
    factor_slice = fm.values[date_idx, :, :]
    
    print(f"\n因子切片形状: {factor_slice.shape}")
    
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
