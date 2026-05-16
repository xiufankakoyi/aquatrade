import time
print("开始", flush=True)

t0 = time.time()
import numpy as np
print(f"numpy: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import pandas as pd
print(f"pandas: {time.time()-t0:.2f}s", flush=True)

print("\n=== 导入核心模块 ===", flush=True)

t0 = time.time()
import sys
sys.path.insert(0, '.')
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
print(f"引擎: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
from core.strategies.simple_test_strategy import SimpleTestStrategy
print(f"策略: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
from data_svc.database.optimized_data_query_arcticdb import OptimizedStockDataQuery
print(f"查询: {time.time()-t0:.2f}s", flush=True)

print("\n完成", flush=True)
