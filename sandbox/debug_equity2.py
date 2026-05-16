#!/usr/bin/env python
"""调试权益曲线问题 - 分析最终结果"""
import sys
sys.path.insert(0, '.')

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from datetime import datetime

print("=== 调试权益曲线问题 ===")

# 初始化
data_query = OptimizedStockDataQuery()
config = BacktestConfig(initial_capital=1000000, commission_rate=0.0003)
engine = UnifiedBacktestEngine(data_query=data_query, config=config)
strategy = MainWaveTrendStrategy()

# 运行回测
results = list(engine.run_backtest(
    start_date='2024-01-01',
    end_date='2024-01-10',
    strategy=strategy
))

print("\n=== _equity_history 内容 ===")
print(f"总记录数: {len(engine._equity_history)}")

# 检查重复
dates = [d for d, _ in engine._equity_history]
from collections import Counter
date_counts = Counter(dates)
dupes = {d: c for d, c in date_counts.items() if c > 1}

if dupes:
    print(f"\n⚠️ 发现重复日期: {dupes}")
    print("\n详细记录:")
    for i, (date, equity) in enumerate(engine._equity_history):
        print(f"  [{i}] {date}: {equity}")
else:
    print("✅ 没有重复日期")
    print("\n前10条记录:")
    for date, equity in engine._equity_history[:10]:
        print(f"  {date}: {equity}")

# 检查 final 结果
final_result = None
for r in results:
    if r.get('type') == 'final':
        final_result = r.get('data', {})
        break

if final_result:
    equity_curve = final_result.get('equity_curve', [])
    print(f"\n=== final 结果中的 equity_curve ===")
    print(f"总记录数: {len(equity_curve)}")
    
    dates = [e.get('date') for e in equity_curve]
    date_counts = Counter(dates)
    dupes = {d: c for d, c in date_counts.items() if c > 1}
    
    if dupes:
        print(f"⚠️ 发现重复日期: {dupes}")
