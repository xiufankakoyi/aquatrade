import time
print("开始", flush=True)

t0 = time.time()
import numpy as np
print(f"numpy: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import pandas as pd
print(f"pandas: {time.time()-t0:.2f}s", flush=True)

print("\n=== 测试numba ===", flush=True)

t0 = time.time()
try:
    import numba
    from numba import jit, njit
    print(f"numba: {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"numba错误: {e}", flush=True)

print("\n=== 导入引擎 ===", flush=True)

t0 = time.time()
import sys
sys.path.insert(0, '.')
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
print(f"引擎: {time.time()-t0:.2f}s", flush=True)

print("\n完成", flush=True)
