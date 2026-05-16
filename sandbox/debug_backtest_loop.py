"""
调试回测循环 - 检查为什么只执行一天
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
print(f"时间序列 ({len(time_series)} 天): {[t.strftime('%Y-%m-%d') for t in time_series]}")

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)
print(f"\n预加载数据完成")

# 检查因子矩阵
if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n因子矩阵信息:")
    print(f"  日期数: {len(fm.dates)}")
    print(f"  日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    print(f"  股票数: {len(fm.codes_str)}")
    print(f"  因子数: {len(fm.factor_names)}")
    print(f"  date_to_idx: {fm.date_to_idx}")
else:
    print("\n因子矩阵为 None")

# 模拟回测循环
print(f"\n{'='*60}")
print("开始模拟回测循环")
print(f"{'='*60}")

for idx, current_time in enumerate(time_series, 1):
    date_str = current_time.strftime('%Y-%m-%d')
    print(f"\nDay {idx}: {date_str}")
    
    # 加载当日数据
    stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
    print(f"  stock_pool type: {type(stock_pool)}")
    print(f"  data_dict 股票数: {len(data_dict) if data_dict else 0}")
    
    if stock_pool is None:
        print(f"  ⚠️ stock_pool is None，跳过这一天！")
        continue
    
    # 检查因子矩阵中的日期索引
    if engine._factor_matrix is not None:
        fm = engine._factor_matrix
        date_idx = fm.date_to_idx.get(date_str, -1)
        print(f"  因子矩阵中日期索引: {date_idx}")
        if date_idx < 0:
            print(f"  ⚠️ 日期 {date_str} 不在因子矩阵中！")
    
    # 生成信号
    signals = engine._generate_signals(
        strategy, current_time, stock_pool, preloaded_data, idx, time_series
    )
    print(f"  信号数: {len(signals)}")
    
    if signals:
        buy_signals = sum(1 for s in signals.values() if s.get('action') == 'buy')
        sell_signals = sum(1 for s in signals.values() if s.get('action') == 'sell')
        print(f"    buy: {buy_signals}, sell: {sell_signals}")

print(f"\n{'='*60}")
print("模拟回测循环结束")
print(f"{'='*60}")
