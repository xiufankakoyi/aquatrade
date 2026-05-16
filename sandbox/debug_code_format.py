"""
调试股票代码格式问题
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

print("=" * 60)
print("调试股票代码格式")
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

print(f"\n因子矩阵中的股票代码格式 (前10个):")
for i, code in enumerate(fm.codes_str[:10]):
    print(f"  {i}: '{code}' (长度: {len(code)})")

# 手动生成信号
strategy.prepare_data(preloaded_data, fm.dates, fm.codes_str, fm.values)
signals = strategy.generate_signals_vectorized(
    fm.values, fm.dates, fm.codes_str, query, preloaded_data
)

# 找到2025-01-02的买入信号
jan2_idx = fm.dates.index('2025-01-02')
buy_signals = []
for i, sig in enumerate(signals[jan2_idx]):
    if sig == 1:  # 买入信号
        buy_signals.append(fm.codes_str[i])

print(f"\n2025-01-02的买入信号 (前10个):")
for i, code in enumerate(buy_signals[:10]):
    print(f"  {i}: '{code}' (长度: {len(code)})")

# 检查data_dict中的代码格式
print(f"\n检查 _build_data_dict_fast 中的代码格式:")

# 模拟调用 _load_day_data
date_str = '2025-01-02'
from datetime import datetime
current_time = pd.to_datetime(date_str)

stock_pool, use_pl, data_dict = engine._load_day_data(current_time)

print(f"\ndata_dict 中的股票代码 (前10个):")
for i, code in enumerate(list(data_dict.keys())[:10]):
    print(f"  {i}: '{code}' (长度: {len(code)})")

# 检查是否有交集
print(f"\n代码匹配检查:")
print(f"  买入信号数量: {len(buy_signals)}")
print(f"  data_dict 中的股票数量: {len(data_dict)}")

# 检查交集
common_codes = set(buy_signals) & set(data_dict.keys())
print(f"  交集数量: {len(common_codes)}")

if len(common_codes) == 0 and len(buy_signals) > 0:
    print(f"\n【问题发现】买入信号和data_dict没有交集!")
    print(f"\n买入信号示例: {buy_signals[:5]}")
    print(f"data_dict 键示例: {list(data_dict.keys())[:5]}")
    
    # 检查格式差异
    print(f"\n格式对比:")
    if buy_signals:
        print(f"  买入信号[0]: '{buy_signals[0]}' (长度{len(buy_signals[0])})")
    if data_dict:
        first_key = list(data_dict.keys())[0]
        print(f"  data_dict键[0]: '{first_key}' (长度{len(first_key)})")
