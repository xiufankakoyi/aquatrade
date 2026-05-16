"""
调试向量化流程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
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

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
print(f"时间序列: {[t.strftime('%Y-%m-%d') for t in time_series]}")

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)
print(f"预加载数据: {preloaded_data is not None}")

# 模拟回测循环
for idx, current_time in enumerate(time_series, 1):
    print(f"\n{'='*60}")
    print(f"Day {idx}: {current_time.strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    
    print(f"  engine._vectorized_mode: {engine._vectorized_mode}")
    print(f"  engine._signal_matrix is not None: {engine._signal_matrix is not None}")
    
    # 加载当日数据
    stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
    print(f"  data_dict 股票数: {len(data_dict) if data_dict else 0}")
    
    # 生成信号
    signals = engine._generate_signals(
        strategy, current_time, stock_pool, preloaded_data, idx, time_series
    )
    print(f"  信号数: {len(signals)}")
    
    if signals:
        buy_signals = sum(1 for s in signals.values() if s.get('action') == 'buy')
        sell_signals = sum(1 for s in signals.values() if s.get('action') == 'sell')
        print(f"    buy: {buy_signals}, sell: {sell_signals}")
