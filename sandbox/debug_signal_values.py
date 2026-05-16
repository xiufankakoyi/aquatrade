"""
调试信号矩阵的值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
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
if not preloaded_data:
    print("预加载数据为空!")
    exit(1)

print(f"预加载数据键: {list(preloaded_data.keys())}")
print(f"stock_daily 行数: {len(preloaded_data['stock_daily'])}")

# 初始化向量化信号
engine._generate_vectorized_signals(strategy, preloaded_data, time_series, time_series[0])

# 检查信号矩阵
print(f"\n信号矩阵形状: {engine._signal_matrix.shape}")
print(f"信号矩阵唯一值: {np.unique(engine._signal_matrix)}")
print(f"买入信号数量 (值=1): {(engine._signal_matrix == 1).sum()}")
print(f"卖出信号数量 (值=2): {(engine._signal_matrix == 2).sum()}")
print(f"零值数量: {(engine._signal_matrix == 0).sum()}")

# 检查每一天的信号
print(f"\n每日信号统计:")
for i, ts in enumerate(time_series):
    date_str = ts.strftime('%Y-%m-%d')
    day_signals = engine._signal_matrix[i]
    buy_count = (day_signals == 1).sum()
    sell_count = (day_signals == 2).sum()
    print(f"  {date_str}: 买入={buy_count}, 卖出={sell_count}")

# 测试 _get_vectorized_signals_for_day
print(f"\n测试 _get_vectorized_signals_for_day:")
for ts in time_series[:3]:
    signals = engine._get_vectorized_signals_for_day(ts)
    buy_signals = {k: v for k, v in signals.items() if v.get('action') == 'buy'}
    sell_signals = {k: v for k, v in signals.items() if v.get('action') == 'sell'}
    print(f"  {ts.strftime('%Y-%m-%d')}: 总信号={len(signals)}, 买入={len(buy_signals)}, 卖出={len(sell_signals)}")
