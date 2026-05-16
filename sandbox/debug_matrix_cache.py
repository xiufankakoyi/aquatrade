"""
测试 MatrixCacheManager
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import numpy as np
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.matrix_cache_manager import get_matrix_cache_manager

# 创建数据管理器
data_manager = UnifiedDataManager()

# 读取数据
df = data_manager.read('stock_daily', start_date='2024-01-02', end_date='2024-01-10')

print(f"原始数据列: {df.columns}")

# 创建缓存管理器
cache_manager = get_matrix_cache_manager()

# 准备数据
preloaded_data = {'stock_daily': df}
trading_dates = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-08', '2024-01-09', '2024-01-10']
stock_codes = df['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()

print(f"\n交易日期: {trading_dates}")
print(f"股票代码数量: {len(stock_codes)}")

# 清除缓存
import shutil
if cache_manager.cache_dir.exists():
    shutil.rmtree(cache_manager.cache_dir, ignore_errors=True)
cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)

# 构建矩阵
result = cache_manager.build_and_save_matrix(preloaded_data, trading_dates, stock_codes)

if result:
    matrices = result['matrices']
    print(f"\n矩阵字段: {list(matrices.keys())}")
    
    # 检查 is_limit_up
    if 'is_limit_up' in matrices:
        limit_up_matrix = matrices['is_limit_up']
        print(f"\nis_limit_up 矩阵:")
        print(f"  形状: {limit_up_matrix.shape}")
        print(f"  类型: {limit_up_matrix.dtype}")
        print(f"  唯一值: {np.unique(limit_up_matrix)}")
        print(f"  True (1): {(limit_up_matrix == 1).sum()}")
        print(f"  False (0): {(limit_up_matrix == 0).sum()}")
    
    # 检查 is_suspended
    if 'is_suspended' in matrices:
        suspended_matrix = matrices['is_suspended']
        print(f"\nis_suspended 矩阵:")
        print(f"  形状: {suspended_matrix.shape}")
        print(f"  类型: {suspended_matrix.dtype}")
        print(f"  唯一值: {np.unique(suspended_matrix)}")
        print(f"  True (1): {(suspended_matrix == 1).sum()}")
        print(f"  False (0): {(suspended_matrix == 0).sum()}")
