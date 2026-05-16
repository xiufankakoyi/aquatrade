"""
调试向量化模式
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

# 模拟回测循环
for idx, current_time in enumerate(time_series, 1):
    print(f"\nDay {idx}: {current_time.strftime('%Y-%m-%d')}")
    print(f"  _vectorized_mode before: {engine._vectorized_mode}")
    
    signals = engine._generate_signals(
        strategy, current_time, None, preloaded, idx, time_series
    )
    
    print(f"  _vectorized_mode after: {engine._vectorized_mode}")
    print(f"  signals count: {len(signals)}")
    
    if idx >= 3:
        break
