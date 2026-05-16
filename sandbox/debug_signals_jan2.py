"""
详细调试2025-01-02的信号生成过程
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
print("详细调试2025-01-02的信号生成")
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
print(f"\n因子矩阵日期: {fm.dates}")
print(f"因子矩阵形状: {fm.values.shape}")

# 手动调用策略的信号生成
print("\n" + "=" * 60)
print("手动调用策略生成信号")
print("=" * 60)

# 准备数据
strategy.prepare_data(preloaded_data, fm.dates, fm.codes_str, fm.values)

print(f"\n数据准备完成:")
print(f"  T (天数): {strategy.T}")
print(f"  N (股票数): {strategy.N}")

# 检查第0天（2024-12-31）和第1天（2025-01-02）的数据
print("\n" + "=" * 60)
print("检查关键数据")
print("=" * 60)

# 找到日期索引
dec31_idx = fm.dates.index('2024-12-31') if '2024-12-31' in fm.dates else -1
jan2_idx = fm.dates.index('2025-01-02') if '2025-01-02' in fm.dates else -1

print(f"\n2024-12-31 索引: {dec31_idx}")
print(f"2025-01-02 索引: {jan2_idx}")

if dec31_idx >= 0 and jan2_idx >= 0:
    # 检查均线数据
    print(f"\n2024-12-31 (第{dec31_idx}天) 均线多头排列数量:")
    ma5_dec31 = strategy.ma5[dec31_idx] if strategy.ma5 is not None else None
    ma10_dec31 = strategy.ma10[dec31_idx] if strategy.ma10 is not None else None
    ma20_dec31 = strategy.ma20[dec31_idx] if strategy.ma20 is not None else None
    
    if ma5_dec31 is not None and ma10_dec31 is not None and ma20_dec31 is not None:
        bullish_dec31 = (ma5_dec31 > ma10_dec31) & (ma10_dec31 > ma20_dec31) & (ma5_dec31 > 0)
        print(f"  {np.sum(bullish_dec31)} 只股票")
    
    # 生成信号
    print("\n" + "=" * 60)
    print("生成信号")
    print("=" * 60)
    
    signals = strategy.generate_signals_vectorized(
        fm.values, fm.dates, fm.codes_str, query, preloaded_data
    )
    
    print(f"\n信号矩阵形状: {signals.shape}")
    print(f"信号值统计:")
    print(f"  买入信号 (1): {np.sum(signals == 1)}")
    print(f"  卖出信号 (2): {np.sum(signals == 2)}")
    print(f"  无信号 (0): {np.sum(signals == 0)}")
    
    # 按天统计
    print(f"\n按天统计信号:")
    for i, date in enumerate(fm.dates):
        buy_count = np.sum(signals[i] == 1)
        sell_count = np.sum(signals[i] == 2)
        if buy_count > 0 or sell_count > 0:
            print(f"  {date}: 买入 {buy_count}, 卖出 {sell_count}")
        else:
            print(f"  {date}: 无信号")
    
    # 特别关注2025-01-02
    if jan2_idx < signals.shape[0]:
        jan2_signals = signals[jan2_idx]
        buy_stocks = np.where(jan2_signals == 1)[0]
        print(f"\n2025-01-02买入信号数量: {len(buy_stocks)}")
        if len(buy_stocks) > 0:
            print(f"前10只买入股票代码:")
            for idx in buy_stocks[:10]:
                print(f"  {fm.codes_str[idx]}")

print("\n" + "=" * 60)
print("结论")
print("=" * 60)
print("""
分析:
1. 数据预加载现在正确包含了2024-12-31
2. 但信号生成可能还有其他问题
3. 需要检查突破/回踩逻辑是否正确处理防止未来函数的偏移
""")
