"""
调试买入信号过滤
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
import numpy as np
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

# 获取时间序列
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)
time_series = engine._get_time_series(start_ts, end_ts)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 初始化向量化信号
engine._generate_vectorized_signals(strategy, preloaded_data, time_series, time_series[0])

# 测试第2天 (2024-01-03)
current_time = time_series[1]
date_str = current_time.strftime('%Y-%m-%d')

# 加载当日数据
stock_pool, use_pl, data_dict = engine._load_day_data(current_time)

# 生成信号
signals = engine._get_vectorized_signals_for_day(current_time)

# 构建 signals_df
signal_rows = []
for code, signal in signals.items():
    sig_type = signal.get('action') if isinstance(signal, dict) else signal
    if sig_type in ('buy', 'enter', 'sell', 'exit'):
        signal_rows.append({
            'code': code,
            'action': 'sell' if sig_type in ('sell', 'exit') else 'buy',
            'indicators': signal.get('indicators', {}) if isinstance(signal, dict) else {}
        })

signals_df = pl.DataFrame(signal_rows)

# 构建 market_df
factor_slice = data_dict['_factor_slice']
fm = engine._factor_matrix

factor_names = fm.factor_names
codes = fm.codes_str
N = len(codes)

factor_idx = {name: i for i, name in enumerate(factor_names)}

def get_col(name, default):
    idx = factor_idx.get(name, -1)
    if idx >= 0:
        col = factor_slice[:, idx]
        return np.nan_to_num(col, nan=default)
    return np.full(N, default)

open_col = get_col('open', 0.0).astype(np.float64)
close_col = get_col('close', 0.0).astype(np.float64)
is_limit_up_col = get_col('is_limit_up', 0).astype(bool)
is_limit_down_col = get_col('is_limit_down', 0).astype(bool)
is_suspended_col = get_col('is_suspended', 0).astype(bool)
total_mv_col = get_col('total_mv', 0.0).astype(np.float64)
adj_factor_col = get_col('adj_factor', 1.0).astype(np.float64)

market_df = pl.DataFrame({
    'code': codes,
    'open': open_col,
    'close': close_col,
    'is_suspended': is_suspended_col,
    'is_limit_up': is_limit_up_col,
    'is_limit_down': is_limit_down_col,
    'adj_factor': adj_factor_col,
    'total_mv': total_mv_col
})

# 测试买入信号过滤
print(f"买入信号过滤测试:")
print("=" * 80)

buy_signals = signals_df.filter(pl.col('action') == 'buy')
print(f"1. 初始买入信号: {len(buy_signals)}")

# 关联市场数据
buy_with_market = buy_signals.join(
    market_df.select(['code', 'open', 'is_suspended', 'is_limit_up']),
    on='code', how='inner'
)
print(f"2. join 后: {len(buy_with_market)}")

# 检查 open 值
print(f"\n   open 值统计:")
print(f"   - open > 0: {(buy_with_market['open'] > 0).sum()}")
print(f"   - open == 0: {(buy_with_market['open'] == 0).sum()}")
print(f"   - open < 0: {(buy_with_market['open'] < 0).sum()}")
print(f"   - open is null: {buy_with_market['open'].is_null().sum()}")

# 检查 is_suspended
print(f"\n   is_suspended 统计:")
print(f"   - True: {(buy_with_market['is_suspended'] == True).sum()}")
print(f"   - False: {(buy_with_market['is_suspended'] == False).sum()}")

# 检查 is_limit_up
print(f"\n   is_limit_up 统计:")
print(f"   - True: {(buy_with_market['is_limit_up'] == True).sum()}")
print(f"   - False: {(buy_with_market['is_limit_up'] == False).sum()}")

# 应用过滤条件
buyable = buy_with_market.filter(
    (pl.col('open') > 0) &
    (pl.col('is_suspended') == False) &
    (pl.col('is_limit_up') == False)
)
print(f"\n3. 过滤后 (open>0, not suspended, not limit_up): {len(buyable)}")

if len(buyable) == 0:
    print("\n   问题: 所有买入信号都被过滤掉了!")
    print("   检查前5个信号的 open 值:")
    for row in buy_with_market.head(5).iter_rows(named=True):
        print(f"   - {row['code']}: open={row['open']}, suspended={row['is_suspended']}, limit_up={row['is_limit_up']}")
