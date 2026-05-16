"""
调试 _execute_trades 参数
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

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 只测试第二天
idx = 2
current_time = time_series[1]  # 2025-06-04

print(f"测试日期: {current_time.strftime('%Y-%m-%d')}")
print(f"idx: {idx}")

# 加载当日数据
stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
print(f"data_dict 股票数: {len(data_dict) if data_dict else 0}")
print(f"stock_pool type: {type(stock_pool)}")
print(f"use_pl: {use_pl}")

# 检查 stock_pool 是否为空
if hasattr(stock_pool, 'empty'):
    print(f"stock_pool.empty: {stock_pool.empty}")
elif isinstance(stock_pool, list):
    print(f"len(stock_pool): {len(stock_pool)}")
elif stock_pool is None:
    print("stock_pool is None")

# 生成信号
signals = engine._generate_signals(
    strategy, current_time, stock_pool, preloaded_data, idx, time_series
)
print(f"信号数: {len(signals)}")

# 检查信号
if signals:
    sample_code = list(signals.keys())[0]
    print(f"样本信号: {sample_code} -> {signals[sample_code]}")
    print(f"样本股票在 data_dict 中: {sample_code in data_dict}")
    if sample_code in data_dict:
        print(f"样本股票数据: {data_dict[sample_code]}")

# 准备执行交易
portfolio = {}
cash = config.initial_capital
position_info = {}

print(f"\n执行交易前:")
print(f"  portfolio: {portfolio}")
print(f"  cash: {cash}")
print(f"  position_info: {position_info}")
print(f"  data_dict is not None: {data_dict is not None}")
print(f"  len(signals) > 0: {len(signals) > 0}")

# 执行交易
if signals and data_dict:
    print("\n调用 _execute_trades...")
    try:
        portfolio, cash, trades = engine._execute_trades(
            current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
        )
        print(f"交易数: {len(trades)}")
        for trade in trades[:3]:
            print(f"  {trade}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
