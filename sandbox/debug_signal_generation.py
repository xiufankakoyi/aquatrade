"""
调试信号生成过程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
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

print("=" * 80)
print("调试信号生成")
print("=" * 80)

# 手动调用回测步骤
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
trading_dates = [ts.strftime('%Y-%m-%d') for ts in time_series]

print(f"\n交易日期: {trading_dates}")

# 获取股票代码
if 'stock_daily' in preloaded_data:
    stock_daily = preloaded_data['stock_daily']
    all_codes = stock_daily['stock_code'].unique().to_list()
    stock_codes_list = sorted(all_codes)
else:
    all_codes = set()
    for df in preloaded_data.values():
        if df is not None and len(df) > 0:
            if hasattr(df, 'is_empty'):
                all_codes.update(df['stock_code'].unique().to_list())
            else:
                all_codes.update(df['stock_code'].unique())
    stock_codes_list = sorted(list(all_codes))

print(f"股票代码数量: {len(stock_codes_list)}")

# 准备数据
strategy.prepare_data(preloaded_data, trading_dates, stock_codes_list)

print(f"\n策略数据准备完成:")
print(f"  T: {strategy.T}")
print(f"  N: {strategy.N}")
print(f"  close 形状: {strategy.close.shape if strategy.close is not None else None}")
print(f"  ma5 形状: {strategy.ma5.shape if strategy.ma5 is not None else None}")
print(f"  ma10 形状: {strategy.ma10.shape if strategy.ma10 is not None else None}")
print(f"  ma20 形状: {strategy.ma20.shape if strategy.ma20 is not None else None}")

# 检查数据是否有 NaN
if strategy.close is not None:
    print(f"\nclose 数据:")
    print(f"  NaN 数量: {np.isnan(strategy.close).sum()}")
    print(f"  非 NaN 数量: {np.isfinite(strategy.close).sum()}")

if strategy.ma5 is not None:
    print(f"\nma5 数据:")
    print(f"  NaN 数量: {np.isnan(strategy.ma5).sum()}")
    print(f"  非 NaN 数量: {np.isfinite(strategy.ma5).sum()}")

# 生成信号
signal_matrix = strategy.generate_signals_vectorized(
    price_matrix=None,
    trading_dates=trading_dates,
    stock_codes=stock_codes_list,
    data_query=data_manager,
    preloaded_data=preloaded_data
)

print(f"\n信号矩阵:")
print(f"  形状: {signal_matrix.shape}")
print(f"  买入信号 (1): {(signal_matrix == 1).sum()}")
print(f"  卖出信号 (2): {(signal_matrix == 2).sum()}")
print(f"  无信号 (0): {(signal_matrix == 0).sum()}")

# 检查每一天的信号
print(f"\n每一天的信号统计:")
for i, date in enumerate(trading_dates):
    day_signals = signal_matrix[i, :]
    buy_count = (day_signals == 1).sum()
    sell_count = (day_signals == 2).sum()
    if buy_count > 0 or sell_count > 0:
        print(f"  {date}: 买入={buy_count}, 卖出={sell_count}")
