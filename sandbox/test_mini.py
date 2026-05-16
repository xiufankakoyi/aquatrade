import time
print("开始", flush=True)

t0 = time.time()
import numpy as np
print(f"numpy: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import pandas as pd
print(f"pandas: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import polars as pl
print(f"polars: {time.time()-t0:.2f}s", flush=True)

print("\n=== 测试小数据回测 ===", flush=True)

t0 = time.time()
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.simple_test_strategy import SimpleTestStrategy
print(f"导入引擎: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
from data_svc.database.optimized_data_query_arcticdb import OptimizedStockDataQuery
print(f"导入查询: {time.time()-t0:.2f}s", flush=True)

print("\n=== 初始化 ===", flush=True)
t0 = time.time()
data_query = OptimizedStockDataQuery(warmup=True)
print(f"数据查询: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
config = BacktestConfig(initial_capital=1_000_000.0, warmup_days=5)
engine = UnifiedBacktestEngine(data_query, config)
print(f"引擎: {time.time()-t0:.2f}s", flush=True)

print(f"\n因子矩阵: {engine._factor_matrix is not None}", flush=True)
if engine._factor_matrix:
    print(f"  dates={len(engine._factor_matrix.dates)}, codes={len(engine._factor_matrix.codes_str)}", flush=True)

print("\n=== 回测3天 ===", flush=True)
strategy = SimpleTestStrategy()

t0 = time.time()
gen = engine.run_backtest_streaming("2024-01-01", "2024-01-03", strategy)
print(f"创建生成器: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
try:
    event = next(gen)
    print(f"事件1 [{event.get('type')}]: {time.time()-t0:.2f}s", flush=True)
except StopIteration:
    print("无事件", flush=True)

t0 = time.time()
try:
    event = next(gen)
    print(f"事件2 [{event.get('type')}]: {time.time()-t0:.2f}s", flush=True)
except StopIteration:
    print("无事件", flush=True)

print("\n完成", flush=True)
