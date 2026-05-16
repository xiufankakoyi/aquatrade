"""
检查信号和data_dict的股票代码格式
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

print("引擎中的股票代码 (前10个):")
print(engine._stock_codes_list[:10])

print("\n信号中的股票代码 (前10个):")
if signals:
    print(list(signals.keys())[:10])
else:
    # 获取第二天的信号
    current_time = time_series[1]
    day_signals = engine._get_vectorized_signals_for_day(current_time)
    print(list(day_signals.keys())[:10])

# 检查因子矩阵中的代码
from core.backtest.factor_matrix import FactorMatrixBuilder
builder = FactorMatrixBuilder()
matrix = builder.build_from_preloaded(preloaded, use_cache=False)

print("\n因子矩阵中的股票代码 (前10个):")
print(matrix.codes_str[:10])

# 检查因子矩阵的codes（原始格式）
print("\n因子矩阵的原始codes (前10个):")
print(matrix.codes[:10])
print(f"类型: {type(matrix.codes[0])}")
