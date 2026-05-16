import time
print("开始", flush=True)

t0 = time.time()
import numpy as np
print(f"numpy: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import pandas as pd
print(f"pandas: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import sys
sys.path.insert(0, '.')

print("测试各个子模块导入...", flush=True)

tests = [
    ("vectorized_base", "from core.strategies.vectorized_base import clear_matrix_cache"),
    ("unified_data_manager", "from data_svc.unified_data_manager import get_unified_manager"),
    ("factor_matrix", "from core.backtest.factor_matrix import build_factor_matrix"),
    ("arcticdb_manager", "from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library"),
]

for name, stmt in tests:
    t0 = time.time()
    try:
        exec(stmt)
        print(f"  {name}: {time.time()-t0:.2f}s", flush=True)
    except Exception as e:
        print(f"  {name}: 错误 - {e}", flush=True)

print("完成", flush=True)
