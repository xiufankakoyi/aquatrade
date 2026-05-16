"""
测试 FactorMatrixBuilder 的 available_factors
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

# 检查 FactorMatrixBuilder 的 factor_names
builder = FactorMatrixBuilder()
print(f"\nFactorMatrixBuilder factor_names: {builder.factor_names}")

# 计算 available_factors
available_factors = [c for c in builder.factor_names if c in df_enhanced.columns]
print(f"\navailable_factors: {available_factors}")

# 检查 is_limit_up 和 is_suspended 的值
if 'is_limit_up' in df_enhanced.columns:
    print(f"\nis_limit_up 值统计:")
    print(f"  唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")
    print(f"  非空值数量: {df_enhanced['is_limit_up'].is_not_null().sum()}")

if 'is_suspended' in df_enhanced.columns:
    print(f"\nis_suspended 值统计:")
    print(f"  唯一值: {df_enhanced['is_suspended'].unique().to_list()}")
    print(f"  非空值数量: {df_enhanced['is_suspended'].is_not_null().sum()}")
