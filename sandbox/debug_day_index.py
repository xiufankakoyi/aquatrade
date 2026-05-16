"""
调试日期索引问题
验证防止未来函数修改后，日期索引是否正确
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
print("调试日期索引问题")
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

print(f"\n因子矩阵日期列表:")
for i, date in enumerate(fm.dates):
    print(f"  索引 {i}: {date}")

print(f"\n关键日期索引:")
print(f"  2024-12-31: {fm.dates.index('2024-12-31') if '2024-12-31' in fm.dates else 'N/A'}")
print(f"  2025-01-02: {fm.dates.index('2025-01-02') if '2025-01-02' in fm.dates else 'N/A'}")
print(f"  2025-01-03: {fm.dates.index('2025-01-03') if '2025-01-03' in fm.dates else 'N/A'}")

# 生成信号
strategy.prepare_data(preloaded_data, fm.dates, fm.codes_str, fm.values)
signals = strategy.generate_signals_vectorized(
    fm.values, fm.dates, fm.codes_str, query, preloaded_data
)

print(f"\n信号矩阵形状: {signals.shape}")
print(f"信号矩阵日期维度对应:")
for i, date in enumerate(fm.dates):
    buy_count = np.sum(signals[i] == 1)
    sell_count = np.sum(signals[i] == 2)
    print(f"  索引 {i} ({date}): 买入 {buy_count}, 卖出 {sell_count}")

print(f"\n【关键分析】")
print(f"2024-12-31 (索引0) 的信号数量: {np.sum(signals[0] == 1)} 买入, {np.sum(signals[0] == 2)} 卖出")
print(f"2025-01-02 (索引1) 的信号数量: {np.sum(signals[1] == 1)} 买入, {np.sum(signals[1] == 2)} 卖出")
print(f"2025-01-03 (索引2) 的信号数量: {np.sum(signals[2] == 1)} 买入, {np.sum(signals[2] == 2)} 卖出")

print(f"\n【防止未来函数的影响】")
print(f"策略使用前一天的数据生成当天的信号:")
print(f"  2025-01-02 的信号基于 2024-12-31 的数据")
print(f"  2025-01-03 的信号基于 2025-01-02 的数据")
print(f"")
print(f"在信号矩阵中:")
print(f"  signals[0] (2024-12-31) 应该是 nan 或 0 (因为没有前一天数据)")
print(f"  signals[1] (2025-01-02) 基于 2024-12-31 的数据")
print(f"  signals[2] (2025-01-03) 基于 2025-01-02 的数据")

# 验证
print(f"\n验证:")
print(f"  signals[0] 买入信号: {np.sum(signals[0] == 1)} (应该为0)")
print(f"  signals[1] 买入信号: {np.sum(signals[1] == 1)} (应该>0)")
print(f"  signals[2] 买入信号: {np.sum(signals[2] == 1)} (应该>0)")
