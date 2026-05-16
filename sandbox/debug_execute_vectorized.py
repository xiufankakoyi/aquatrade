"""
调试 _execute_trades_vectorized
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
print("调试 _execute_trades_vectorized")
print("=" * 80)

# 手动调用回测步骤
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 先生成向量化信号（第一天）
print("\n第一步：生成向量化信号")
first_day_signals = engine._generate_vectorized_signals(
    strategy, preloaded_data, time_series, time_series[0]
)

print(f"第一天信号数量: {len(first_day_signals)}")
print(f"_vectorized_mode: {engine._vectorized_mode}")
print(f"_signal_matrix 形状: {engine._signal_matrix.shape if engine._signal_matrix is not None else None}")

# 模拟第二天
current_time = time_series[1]  # 2024-01-03
date_str = current_time.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"日期: {date_str}")
print(f"{'='*60}")

# 加载当日数据
stock_pool, use_pl, data_dict = engine._load_day_data(current_time)

# 生成信号（第二天及以后）
signals = engine._get_vectorized_signals_for_day(current_time)

print(f"\n信号数量: {len(signals)}")

buy_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'buy'}
sell_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'sell'}

print(f"买入信号: {len(buy_signals)}")
print(f"卖出信号: {len(sell_signals)}")

if buy_signals:
    print(f"买入股票示例: {list(buy_signals.keys())[:5]}")

# 检查 _factor_matrix
if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n_factor_matrix 信息:")
    print(f"  形状: {fm.values.shape}")
    print(f"  日期数: {len(fm.dates)}")
    print(f"  股票代码数: {len(fm.codes_str)}")

# 检查 _factor_slice
if '_factor_slice' in data_dict:
    factor_slice = data_dict['_factor_slice']
    print(f"\n_factor_slice 信息:")
    print(f"  形状: {factor_slice.shape}")
    print(f"  类型: {factor_slice.dtype}")
    
    # 检查 is_limit_up 和 is_suspended
    if 'is_limit_up' in engine._factor_matrix.factor_names:
        is_limit_up_idx = engine._factor_matrix.factor_names.index('is_limit_up')
        is_limit_up_col = factor_slice[:, is_limit_up_idx]
        print(f"\nis_limit_up 列:")
        print(f"  唯一值数量: {len(np.unique(is_limit_up_col))}")
        print(f"  最小值: {np.nanmin(is_limit_up_col)}")
        print(f"  最大值: {np.nanmax(is_limit_up_col)}")
        print(f"  True (1): {(is_limit_up_col == 1).sum()}")
        print(f"  False (0): {(is_limit_up_col == 0).sum()}")
    
    if 'is_suspended' in engine._factor_matrix.factor_names:
        is_suspended_idx = engine._factor_matrix.factor_names.index('is_suspended')
        is_suspended_col = factor_slice[:, is_suspended_idx]
        print(f"\nis_suspended 列:")
        print(f"  唯一值数量: {len(np.unique(is_suspended_col))}")
        print(f"  True (1): {(is_suspended_col == 1).sum()}")
        print(f"  False (0): {(is_suspended_col == 0).sum()}")

# 执行交易
portfolio = {}
cash = config.initial_capital
position_info = {}

new_portfolio, new_cash, trades = engine._execute_trades(
    current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
)

print(f"\n交易执行结果:")
print(f"  新持仓数: {len(new_portfolio)}")
print(f"  新现金: {new_cash:,.2f}")
print(f"  交易数: {len(trades)}")

if trades:
    print("\n交易列表:")
    for trade in trades:
        print(f"  {trade.action.upper()} {trade.code} {trade.shares}股 @ {trade.price:.2f}")
