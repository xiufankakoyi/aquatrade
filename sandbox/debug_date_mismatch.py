"""
调试日期索引不匹配问题
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import pandas as pd
import numpy as np

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

print("=" * 60)
print("调试日期索引不匹配问题")
print("=" * 60)

# 预加载数据
start_date = '2025-01-02'
end_date = '2025-01-05'
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

preloaded_data = engine._preload_data(start_ts, end_ts)

if engine._factor_matrix is None:
    print("因子矩阵为空!")
    sys.exit(1)

fm = engine._factor_matrix

print(f"\n因子矩阵日期: {fm.dates}")
print(f"因子矩阵形状: {fm.values.shape}")

# 模拟 time_series (回测日期，不包含 warmup)
time_series = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日
time_series = [ts for ts in time_series if ts.strftime('%Y-%m-%d') in ['2025-01-02', '2025-01-03']]

print(f"\n模拟 time_series (回测日期):")
for i, ts in enumerate(time_series):
    print(f"  {i}: {ts.strftime('%Y-%m-%d')}")

# 模拟 _generate_vectorized_signals 中的逻辑
trading_dates = [ts.strftime("%Y-%m-%d") for ts in time_series]
print(f"\ntrading_dates: {trading_dates}")

# 模拟 _date_to_idx 的构建
date_to_idx = {d: i for i, d in enumerate(trading_dates)}
print(f"\n_date_to_idx (基于 trading_dates): {date_to_idx}")

# 现在检查信号获取
print(f"\n【问题分析】")
print(f"当获取 2025-01-02 的信号时:")
t_idx = date_to_idx.get('2025-01-02', -1)
print(f"  t_idx = date_to_idx.get('2025-01-02') = {t_idx}")
print(f"  但信号矩阵中索引 {t_idx} 对应的是 '{fm.dates[t_idx]}'")
print(f"  而 2025-01-02 的信号实际上在索引 {fm.dates.index('2025-01-02')}")

print(f"\n【正确做法】")
print(f"应该使用因子矩阵的日期索引，而不是 trading_dates 的索引:")
fm_date_to_idx = {d: i for i, d in enumerate(fm.dates)}
print(f"  fm_date_to_idx: {fm_date_to_idx}")
print(f"  fm_date_to_idx.get('2025-01-02') = {fm_date_to_idx.get('2025-01-02')}")
print(f"  这才是正确的索引!")
