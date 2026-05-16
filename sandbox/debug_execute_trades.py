"""
调试 _execute_trades 方法
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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

# 运行回测
print("=" * 80)
print("调试 _execute_trades")
print("=" * 80)

# 手动调用回测步骤
from datetime import datetime

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
print(f"\n时间序列: {[ts.strftime('%Y-%m-%d') for ts in time_series]}")

# 生成向量化信号
current_time = time_series[0]
signals = engine._generate_vectorized_signals(strategy, preloaded_data, time_series, current_time)

print(f"\n信号数量: {len(signals)}")

# 检查信号
buy_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'buy'}
sell_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'sell'}

print(f"买入信号: {len(buy_signals)}")
print(f"卖出信号: {len(sell_signals)}")

# 加载当日数据
stock_pool, use_pl, data_dict = engine._load_day_data(current_time)

print(f"\n股票池类型: {type(stock_pool)}")
print(f"使用 Polars: {use_pl}")
print(f"data_dict 键: {list(data_dict.keys())[:5]}")

# 检查 _factor_matrix
if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n_factor_matrix 信息:")
    print(f"  形状: {fm.values.shape}")
    print(f"  日期数: {len(fm.dates)}")
    print(f"  股票代码数: {len(fm.codes_str)}")
    
    # 检查 is_limit_up 和 is_suspended
    if 'is_limit_up' in fm.factor_names:
        is_limit_up_idx = fm.factor_names.index('is_limit_up')
        print(f"  is_limit_up 索引: {is_limit_up_idx}")
    
    if 'is_suspended' in fm.factor_names:
        is_suspended_idx = fm.factor_names.index('is_suspended')
        print(f"  is_suspended 索引: {is_suspended_idx}")

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
