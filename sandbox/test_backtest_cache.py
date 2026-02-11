#!/usr/bin/env python3
"""
测试回测结果缓存性能
"""

import time
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
from core.strategies.strategy_factory import get_factory

# 初始化数据查询和回测引擎
data_query = OptimizedStockDataQuery()
engine = OptimizedBacktestEngine(data_query)

# 获取策略工厂
factory = get_factory()

# 选择第一个可用的策略
strategies = factory.list_strategies()
if not strategies:
    print("没有可用的策略")
    exit(1)

strategy_name = strategies[0]['name']
print(f"使用策略: {strategy_name}")

# 创建策略实例
strategy = factory.create_strategy(strategy_name)

# 回测日期范围
start_date = "2024-02-20"
end_date = "2025-01-15"

# 第一次回测（应该不命中缓存）
print(f"\n第一次回测: {start_date} 到 {end_date}")
t1 = time.time()
results1 = list(engine.run_backtest_streaming(start_date, end_date, strategy))
t2 = time.time()
first_time = t2 - t1
print(f"第一次回测耗时: {first_time:.2f} 秒")

# 第二次回测（应该命中缓存）
print(f"\n第二次回测: {start_date} 到 {end_date}")
t3 = time.time()
results2 = list(engine.run_backtest_streaming(start_date, end_date, strategy))
t4 = time.time()
second_time = t4 - t3
print(f"第二次回测耗时: {second_time:.2f} 秒")

# 输出性能提升
improvement = first_time / second_time if second_time > 0 else 0
print(f"\n性能提升: {improvement:.2f} 倍")
print(f"节省时间: {first_time - second_time:.2f} 秒")
