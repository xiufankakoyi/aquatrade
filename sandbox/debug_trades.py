"""
调试交易执行
"""
import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.config import Config

# 创建数据查询
print("初始化数据查询...")
data_query = OptimizedStockDataQuery()

# 创建策略实例
strategy = MainWaveTrendStrategy()

# 创建回测配置
backtest_config = BacktestConfig(
    initial_capital=Config.INITIAL_CAPITAL,
    commission_rate=Config.COMMISSION_RATE,
    min_commission=Config.MIN_COMMISSION,
    sell_tax=Config.SELL_TAX
)

# 创建回测引擎
engine = UnifiedBacktestEngine(
    data_query=data_query,
    config=backtest_config
)

# 运行回测
start_date = "2024-01-02"
end_date = "2024-01-10"

print(f"开始回测: {start_date} 到 {end_date}")
print("=" * 80)

# 手动执行回测步骤来调试
from data_svc.unified_data_manager import get_unified_manager

manager = get_unified_manager()
preloaded_data = manager.preload_to_memory(start_date=start_date, end_date=end_date)

# 获取交易日
trading_dates = data_query.get_trading_dates(start_date, end_date)
time_series = [pd.to_datetime(d) for d in trading_dates]

print(f"交易日数量: {len(trading_dates)}")

# 调用 _generate_vectorized_signals 初始化信号矩阵
print("\n初始化向量化信号...")
signals_day1 = engine._generate_vectorized_signals(
    strategy=strategy,
    preloaded_data=preloaded_data,
    time_series=time_series,
    current_time=time_series[0]
)

print(f"第一天信号数量: {len(signals_day1)}")
print(f"买入信号: {sum(1 for s in signals_day1.values() if s.get('action') == 'buy')}")
print(f"卖出信号: {sum(1 for s in signals_day1.values() if s.get('action') == 'sell')}")

# 检查引擎内部状态
print(f"\n引擎内部状态:")
print(f"  _vectorized_mode: {engine._vectorized_mode}")
print(f"  _signal_matrix: {engine._signal_matrix is not None}")
if engine._signal_matrix is not None:
    print(f"  信号矩阵形状: {engine._signal_matrix.shape}")
    print(f"  买入信号总数: {np.sum(engine._signal_matrix == 1)}")
    print(f"  卖出信号总数: {np.sum(engine._signal_matrix == 2)}")

# 测试每一天的信号获取
print(f"\n每天信号统计:")
for i in range(min(5, len(time_series))):
    day_signals = engine._get_vectorized_signals_for_day(time_series[i])
    buy_count = sum(1 for s in day_signals.values() if s.get('action') == 'buy')
    sell_count = sum(1 for s in day_signals.values() if s.get('action') == 'sell')
    print(f"  {trading_dates[i]}: 信号数={len(day_signals)}, 买入={buy_count}, 卖出={sell_count}")
    
    # 如果有买入信号，显示前几个
    if buy_count > 0:
        buy_signals = {k: v for k, v in day_signals.items() if v.get('action') == 'buy'}
        print(f"    买入信号股票 (前5): {list(buy_signals.keys())[:5]}")

# 检查 _generate_signals 方法在后续日期的调用
print(f"\n测试 _generate_signals 方法:")
for idx in range(1, min(4, len(time_series) + 1)):
    current_time = time_series[idx - 1]
    
    # 模拟调用 _generate_signals
    signals = engine._generate_signals(
        strategy=strategy,
        current_time=current_time,
        stock_pool=None,  # 不需要股票池
        preloaded_data=preloaded_data,
        idx=idx,
        time_series=time_series
    )
    
    buy_count = sum(1 for s in signals.values() if s.get('action') == 'buy')
    sell_count = sum(1 for s in signals.values() if s.get('action') == 'sell')
    print(f"  Day {idx} ({trading_dates[idx-1]}): 信号数={len(signals)}, 买入={buy_count}, 卖出={sell_count}")
