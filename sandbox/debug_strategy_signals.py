"""
调试策略信号生成
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.factor_matrix import FactorMatrixBuilder
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import numpy as np

query = OptimizedStockDataQuery()

# 预加载数据
query.preload_backtest_data('2025-06-01', '2025-06-30')
preloaded = getattr(query, '_preloaded_data', None)

if preloaded:
    print(f"预加载数据: {len(preloaded)} 个日期")
    
    # 构建因子矩阵
    builder = FactorMatrixBuilder()
    matrix = builder.build_from_preloaded(preloaded, use_cache=False)
    
    print(f"\n因子矩阵: T={matrix.values.shape[0]}, N={matrix.values.shape[1]}")
    
    # 创建策略
    strategy = MainWaveTrendStrategy(
        data_manager=query,
        lookback_days=20,
        breakout_days=5,
        volume_threshold=1.5,
        trend_period=20
    )
    
    # 准备因子数据
    factor_data = {}
    for i, name in enumerate(matrix.factor_names):
        factor_data[name] = matrix.values[:, :, i]
    
    # 设置策略数据
    strategy.set_factor_data(factor_data)
    strategy.codes = matrix.codes_str
    strategy.dates = matrix.dates
    
    print(f"\n策略数据:")
    print(f"  股票数: {len(strategy.codes)}")
    print(f"  日期数: {len(strategy.dates)}")
    print(f"  close shape: {strategy.close.shape if strategy.close is not None else None}")
    
    # 生成信号
    signals = strategy.generate_signals_vectorized()
    
    print(f"\n信号统计:")
    print(f"  买入信号 (1): {np.sum(signals == 1)}")
    print(f"  卖出信号 (2): {np.sum(signals == 2)}")
    print(f"  无信号 (0): {np.sum(signals == 0)}")
    
    # 检查具体哪些天有信号
    print(f"\n每日信号统计:")
    for t in range(min(10, signals.shape[0])):
        buy_count = np.sum(signals[t] == 1)
        sell_count = np.sum(signals[t] == 2)
        if buy_count > 0 or sell_count > 0:
            print(f"  {strategy.dates[t]}: 买入={buy_count}, 卖出={sell_count}")
else:
    print("没有预加载数据")
