#!/usr/bin/env python
"""测试回测数据 - 详细分析"""
import sys
sys.path.insert(0, '.')

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from datetime import datetime

print("=== 测试 main_wave_trend 策略 ===")
print(f"开始时间: {datetime.now()}")

# 初始化数据查询
data_query = OptimizedStockDataQuery()

# 初始化回测引擎
config = BacktestConfig(
    initial_capital=1000000,
    commission_rate=0.0003
)
engine = UnifiedBacktestEngine(data_query=data_query, config=config)

# 初始化策略
strategy = MainWaveTrendStrategy()

# 运行回测
results = list(engine.run_backtest(
    start_date='2024-01-01',
    end_date='2024-01-10',  # 只测试前10天
    strategy=strategy
))

# 分析权益曲线事件
equity_events = [r for r in results if r.get('type') == 'daily_equity_engine']
print(f"\n=== 权益曲线事件 ({len(equity_events)} 个) ===")
for e in equity_events[:10]:
    data = e.get('data', {})
    print(f"  {data.get('date')}: equity={data.get('equity')}, cash={data.get('cash')}, positions={data.get('positions')}")

# 检查是否有重复日期
dates = [e.get('data', {}).get('date') for e in equity_events]
unique_dates = set(dates)
if len(dates) != len(unique_dates):
    print(f"\n⚠️ 发现重复日期! 总记录: {len(dates)}, 唯一日期: {len(unique_dates)}")
    from collections import Counter
    dupes = {d: c for d, c in Counter(dates).items() if c > 1}
    print(f"重复日期: {dupes}")
else:
    print(f"\n✅ 没有重复日期")

print(f"\n结束时间: {datetime.now()}")
