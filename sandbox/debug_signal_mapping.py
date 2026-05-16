"""
检查信号映射问题
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
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

start_date = '2025-06-03'
end_date = '2025-06-10'

# 手动调用 _generate_vectorized_signals
from datetime import datetime
import pandas as pd

time_series = pd.date_range(start=start_date, end=end_date, freq='B')
print(f"交易日序列: {len(time_series)} 天")
for i, ts in enumerate(time_series):
    print(f"  {i}: {ts.strftime('%Y-%m-%d')}")

# 预加载数据
query.preload_backtest_data(start_date, end_date)
preloaded = getattr(query, '_preloaded_data', None)

if preloaded:
    print(f"\n预加载数据日期:")
    for date in sorted(preloaded.keys())[:10]:
        print(f"  {date}")
    
    # 手动调用向量化信号生成
    current_time = time_series[0]
    signals = engine._generate_vectorized_signals(strategy, preloaded, time_series, current_time)
    
    print(f"\n第一次调用 _generate_vectorized_signals 返回的信号数: {len(signals)}")
    
    # 检查引擎状态
    print(f"\n引擎状态:")
    print(f"  _vectorized_mode: {engine._vectorized_mode}")
    print(f"  _signal_matrix shape: {engine._signal_matrix.shape if engine._signal_matrix is not None else None}")
    print(f"  _date_to_idx: {engine._date_to_idx}")
    print(f"  _stock_codes_list: {len(engine._stock_codes_list)} 只股票")
    
    # 检查信号矩阵
    signal_matrix = engine._signal_matrix
    if signal_matrix is not None:
        print(f"\n信号矩阵统计:")
        for t in range(signal_matrix.shape[0]):
            buy_count = np.sum(signal_matrix[t] == 1)
            sell_count = np.sum(signal_matrix[t] == 2)
            print(f"  Day {t}: 买入={buy_count}, 卖出={sell_count}")
    
    # 测试 _get_vectorized_signals_for_day
    print(f"\n测试 _get_vectorized_signals_for_day:")
    for i, ts in enumerate(time_series[:5]):
        day_signals = engine._get_vectorized_signals_for_day(ts)
        print(f"  {ts.strftime('%Y-%m-%d')}: {len(day_signals)} 个信号")
