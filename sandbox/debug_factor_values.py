"""
调试因子矩阵中的 is_suspended 和 is_limit_up 值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
import numpy as np
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

# 创建数据管理器
data_manager = UnifiedDataManager()

# 创建回测配置
config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

# 创建回测引擎
engine = UnifiedBacktestEngine(
    data_query=data_manager,
    config=config
)

# 创建策略
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

# 设置回测区间
start_date = '2024-01-02'
end_date = '2024-01-10'

# 获取时间序列
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)
time_series = engine._get_time_series(start_ts, end_ts)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 初始化向量化信号
engine._generate_vectorized_signals(strategy, preloaded_data, time_series, time_series[0])

# 获取因子矩阵
fm = engine._factor_matrix
print(f"因子矩阵信息:")
print(f"  形状: {fm.values.shape}")
print(f"  因子名称: {fm.factor_names}")

# 检查 is_suspended 和 is_limit_up 的索引
is_suspended_idx = fm.factor_names.index('is_suspended') if 'is_suspended' in fm.factor_names else -1
is_limit_up_idx = fm.factor_names.index('is_limit_up') if 'is_limit_up' in fm.factor_names else -1
is_limit_down_idx = fm.factor_names.index('is_limit_down') if 'is_limit_down' in fm.factor_names else -1

print(f"\n因子索引:")
print(f"  is_suspended: {is_suspended_idx}")
print(f"  is_limit_up: {is_limit_up_idx}")
print(f"  is_limit_down: {is_limit_down_idx}")

# 检查第2天 (2024-01-03) 的数据
date_str = '2024-01-03'
date_idx = fm.date_to_idx.get(date_str, -1)
print(f"\n日期 {date_str} 的索引: {date_idx}")

if date_idx >= 0:
    factor_slice = fm.values[date_idx, :, :]
    
    print(f"\n因子切片形状: {factor_slice.shape}")
    
    if is_suspended_idx >= 0:
        suspended_col = factor_slice[:, is_suspended_idx]
        print(f"\nis_suspended 值统计:")
        print(f"  唯一值: {np.unique(suspended_col)}")
        print(f"  True (1.0): {(suspended_col == 1.0).sum()}")
        print(f"  False (0.0): {(suspended_col == 0.0).sum()}")
        print(f"  NaN: {np.isnan(suspended_col).sum()}")
        print(f"  其他: {len(suspended_col) - (suspended_col == 1.0).sum() - (suspended_col == 0.0).sum() - np.isnan(suspended_col).sum()}")
    
    if is_limit_up_idx >= 0:
        limit_up_col = factor_slice[:, is_limit_up_idx]
        print(f"\nis_limit_up 值统计:")
        print(f"  唯一值: {np.unique(limit_up_col)}")
        print(f"  True (1.0): {(limit_up_col == 1.0).sum()}")
        print(f"  False (0.0): {(limit_up_col == 0.0).sum()}")
        print(f"  NaN: {np.isnan(limit_up_col).sum()}")
    
    # 检查 open 和 close
    open_idx = fm.factor_names.index('open') if 'open' in fm.factor_names else -1
    close_idx = fm.factor_names.index('close') if 'close' in fm.factor_names else -1
    
    if open_idx >= 0:
        open_col = factor_slice[:, open_idx]
        print(f"\nopen 值统计:")
        print(f"  NaN: {np.isnan(open_col).sum()}")
        print(f"  0: {(open_col == 0).sum()}")
        print(f"  >0: {(open_col > 0).sum()}")
