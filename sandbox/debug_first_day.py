"""
调试第一天的信号
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
print("调试第一天的信号")
print("=" * 80)

# 手动调用回测步骤
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)

print(f"\n时间序列: {[ts.strftime('%Y-%m-%d') for ts in time_series]}")

# 生成向量化信号
current_time = time_series[0]
signals = engine._generate_vectorized_signals(strategy, preloaded_data, time_series, current_time)

print(f"\n第一天 ({current_time.strftime('%Y-%m-%d')}) 信号:")
print(f"  信号数量: {len(signals)}")

# 检查信号矩阵
if engine._signal_matrix is not None:
    signal_matrix = engine._signal_matrix
    print(f"\n信号矩阵:")
    print(f"  形状: {signal_matrix.shape}")
    print(f"  买入信号 (1): {(signal_matrix == 1).sum()}")
    print(f"  卖出信号 (2): {(signal_matrix == 2).sum()}")
    
    # 检查每一天的信号
    print(f"\n每一天的信号统计:")
    for i, ts in enumerate(time_series):
        date_str = ts.strftime('%Y-%m-%d')
        day_signals = signal_matrix[i, :]
        buy_count = (day_signals == 1).sum()
        sell_count = (day_signals == 2).sum()
        print(f"  {date_str}: 买入={buy_count}, 卖出={sell_count}")

# 检查 _date_to_idx
print(f"\n_date_to_idx:")
for date, idx in engine._date_to_idx.items():
    print(f"  {date}: {idx}")
