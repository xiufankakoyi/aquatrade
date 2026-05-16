"""
调试2025年1月2号的买入情况
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

# 检查2025年1月2号前后的数据
start_date = '2024-12-20'  # 提前一些，确保有足够的历史数据
end_date = '2025-01-10'

print("=" * 60)
print(f"调试2025年1月2号: {start_date} ~ {end_date}")
print("=" * 60)

# 先检查数据是否存在
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)
preloaded_data = engine._preload_data(start_ts, end_ts)

if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n因子矩阵日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    print(f"总天数: {len(fm.dates)}")
    print(f"所有日期: {fm.dates}")
    
    # 找到2025-01-02的索引 - 注意格式是 '20250102'
    target_date = '20250102'
    print(f"\n查找日期: {target_date}")
    print(f"日期是否在列表中: {target_date in fm.dates}")
    
    if target_date in fm.dates:
        idx = fm.dates.index(target_date)
        print(f"\n2025-01-02的索引: {idx}")
        
        # 查看当天的数据
        factor_slice = fm.values[idx, :, :]
        close_idx = fm.factor_names.index('close') if 'close' in fm.factor_names else -1
        ma5_idx = fm.factor_names.index('ma5') if 'ma5' in fm.factor_names else -1
        ma10_idx = fm.factor_names.index('ma10') if 'ma10' in fm.factor_names else -1
        ma20_idx = fm.factor_names.index('ma20') if 'ma20' in fm.factor_names else -1
        
        if close_idx >= 0:
            close_data = factor_slice[:, close_idx]
            valid_close = close_data[~np.isnan(close_data)]
            print(f"\n2025-01-02收盘价统计:")
            print(f"  有效数据: {len(valid_close)}/{len(close_data)}")
            if len(valid_close) > 0:
                print(f"  价格范围: {np.min(valid_close):.2f} ~ {np.max(valid_close):.2f}")
        
        if ma5_idx >= 0 and ma10_idx >= 0 and ma20_idx >= 0:
            ma5_data = factor_slice[:, ma5_idx]
            ma10_data = factor_slice[:, ma10_idx]
            ma20_data = factor_slice[:, ma20_idx]
            
            # 计算均线多头排列的股票数量
            bullish = (ma5_data > ma10_data) & (ma10_data > ma20_data) & (ma5_data > 0)
            bullish_count = np.sum(bullish)
            print(f"\n2025-01-02均线多头排列: {bullish_count} 只股票")
            
            # 查看前一天（12-31）的数据 - 【防止未来函数】策略使用的是前一天的数据
            prev_date = '20241231'
            if prev_date in fm.dates:
                prev_idx = fm.dates.index(prev_date)
                prev_slice = fm.values[prev_idx, :, :]
                prev_close = prev_slice[:, close_idx]
                prev_ma5 = prev_slice[:, ma5_idx]
                prev_ma10 = prev_slice[:, ma10_idx]
                prev_ma20 = prev_slice[:, ma20_idx]
                
                prev_bullish = (prev_ma5 > prev_ma10) & (prev_ma10 > prev_ma20) & (prev_ma5 > 0)
                prev_bullish_count = np.sum(prev_bullish)
                print(f"\n前一天(2024-12-31)均线多头排列: {prev_bullish_count} 只股票")
                
                # 【防止未来函数】策略使用的是前一天的数据
                print(f"\n【防止未来函数】2025-01-02的信号基于2024-12-31的数据")
                print(f"  前一天有效收盘价: {np.sum(~np.isnan(prev_close))}")
                print(f"  前一天均线多头排列: {prev_bullish_count}")
            else:
                print(f"\n【关键问题】前一天(2024-12-31)不在数据中!")
                print(f"  这意味着2025-01-02无法生成信号（没有前一天数据）")
    else:
        print(f"\n2025-01-02不在因子矩阵中!")
        print(f"可用日期: {fm.dates}")

# 运行回测查看详细事件
print("\n" + "=" * 60)
print("运行回测查看2025-01-02的事件:")
print("=" * 60)

# 使用更长的回测周期，确保有足够的历史数据
event_count = 0
trades_on_jan2 = []

for event in engine.run_backtest(strategy=strategy, start_date='2024-12-20', end_date='2025-01-10'):
    event_count += 1
    event_type = event.get('type')
    
    if event_type == 'backtest_start':
        print(f"\n[事件 {event_count}] 回测开始")
        print(f"  交易日数量: {len(event['data'].get('trading_dates', []))}")
    
    elif event_type == 'new_trade_engine':
        t = event['data']
        if t['date'] == '20250102':
            trades_on_jan2.append(t)
            print(f"[事件 {event_count}] 2025-01-02交易: {t['code']} {t['action']} {t['shares']}股 @ {t['price']:.2f}")

print(f"\n2025-01-02的交易数量: {len(trades_on_jan2)}")

if len(trades_on_jan2) == 0:
    print("\n" + "=" * 60)
    print("分析: 为什么2025-01-02没有买入?")
    print("=" * 60)
    print("""
可能的原因:
1. 【防止未来函数】2025-01-02的信号基于2024-12-31的数据
2. 2024-12-31可能没有满足条件的股票（均线多头排列等）
3. 或者2024-12-31是节假日，没有交易数据

建议检查:
- 2024-12-31是否是交易日
- 2024-12-31有多少只股票满足买入条件
    """)
