#!/usr/bin/env python
"""调试权益曲线问题"""
import sys
sys.path.insert(0, '.')

# 修改 UnifiedBacktestEngine 来追踪 _equity_history 的追加
from core.backtest.unified_engine import UnifiedBacktestEngine

# 保存原始方法
original_append = list.append

# 追踪 _equity_history 的追加
def tracked_append(self, item):
    if len(self) > 0 and self[0] == '2024-01-02':  # 检查是否是权益曲线
        print(f"[TRACK] _equity_history.append({item})")
        import traceback
        traceback.print_stack(limit=8)
    return original_append(self, item)

# 运行测试
from core.backtest.unified_engine import BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from datetime import datetime

print("=== 调试权益曲线问题 ===")

# 初始化
data_query = OptimizedStockDataQuery()
config = BacktestConfig(initial_capital=1000000, commission_rate=0.0003)
engine = UnifiedBacktestEngine(data_query=data_query, config=config)

# 替换 append 方法
import types
engine._equity_history.append = types.MethodType(tracked_append, engine._equity_history)

strategy = MainWaveTrendStrategy()

# 只测试前几天
results = list(engine.run_backtest(
    start_date='2024-01-01',
    end_date='2024-01-05',
    strategy=strategy
))

print("\n=== 权益曲线历史 ===")
for date, equity in engine._equity_history:
    print(f"  {date}: {equity}")
