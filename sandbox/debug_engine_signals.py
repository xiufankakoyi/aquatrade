"""
调试引擎信号生成
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import numpy as np
import pandas as pd

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

start_date = '2025-06-03'
end_date = '2025-06-10'

# 预加载数据
query.preload_backtest_data(start_date, end_date)
preloaded = getattr(query, '_preloaded_data', None)

time_series = pd.date_range(start=start_date, end=end_date, freq='B')
current_time = time_series[0]

# 手动调用向量化信号生成
signals = engine._generate_vectorized_signals(strategy, preloaded, time_series, current_time)

print(f"第一天信号数: {len(signals)}")

# 检查引擎状态
print(f"\n引擎状态:")
print(f"  _vectorized_mode: {engine._vectorized_mode}")
print(f"  _signal_matrix shape: {engine._signal_matrix.shape if engine._signal_matrix is not None else None}")
print(f"  _stock_codes_list (前10个): {engine._stock_codes_list[:10] if engine._stock_codes_list else None}")

# 检查第二天的信号
current_time = time_series[1]
day_signals = engine._get_vectorized_signals_for_day(current_time)
print(f"\n第二天信号数: {len(day_signals)}")

# 检查信号中的代码格式
if day_signals:
    print(f"信号中的代码 (前10个): {list(day_signals.keys())[:10]}")
