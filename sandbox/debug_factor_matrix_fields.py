"""
调试 FactorMatrix 中的状态字段
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
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

print("=" * 80)
print("调试 FactorMatrix 中的状态字段")
print("=" * 80)

# 手动调用回测步骤
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)

# 生成向量化信号（这会构建 FactorMatrix）
first_day_signals = engine._generate_vectorized_signals(
    strategy, preloaded_data, time_series, time_series[0]
)

# 检查 FactorMatrix
if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\nFactorMatrix 信息:")
    print(f"  形状: {fm.values.shape}")
    print(f"  日期数: {len(fm.dates)}")
    print(f"  股票代码数: {len(fm.codes_str)}")
    print(f"  因子名称: {fm.factor_names}")
    
    # 检查 is_limit_up 字段
    if 'is_limit_up' in fm.factor_names:
        is_limit_up_idx = fm.factor_names.index('is_limit_up')
        is_limit_up_matrix = fm.values[:, :, is_limit_up_idx]
        
        print(f"\nis_limit_up 矩阵:")
        print(f"  形状: {is_limit_up_matrix.shape}")
        print(f"  类型: {is_limit_up_matrix.dtype}")
        print(f"  最小值: {np.nanmin(is_limit_up_matrix)}")
        print(f"  最大值: {np.nanmax(is_limit_up_matrix)}")
        print(f"  唯一值数量: {len(np.unique(is_limit_up_matrix[~np.isnan(is_limit_up_matrix)]))}")
        
        # 检查第二天
        date_str = '2024-01-03'
        if date_str in fm.date_to_idx:
            t_idx = fm.date_to_idx[date_str]
            day_is_limit_up = is_limit_up_matrix[t_idx, :]
            
            print(f"\n{date_str} 的 is_limit_up:")
            print(f"  唯一值: {np.unique(day_is_limit_up[~np.isnan(day_is_limit_up)])}")
            print(f"  True (非零): {(day_is_limit_up != 0).sum()}")
            print(f"  False (零): {(day_is_limit_up == 0).sum()}")
            print(f"  NaN: {np.isnan(day_is_limit_up).sum()}")
    
    # 检查 is_suspended 字段
    if 'is_suspended' in fm.factor_names:
        is_suspended_idx = fm.factor_names.index('is_suspended')
        is_suspended_matrix = fm.values[:, :, is_suspended_idx]
        
        print(f"\nis_suspended 矩阵:")
        print(f"  形状: {is_suspended_matrix.shape}")
        print(f"  类型: {is_suspended_matrix.dtype}")
        print(f"  最小值: {np.nanmin(is_suspended_matrix)}")
        print(f"  最大值: {np.nanmax(is_suspended_matrix)}")
        print(f"  唯一值: {np.unique(is_suspended_matrix[~np.isnan(is_suspended_matrix)])}")
