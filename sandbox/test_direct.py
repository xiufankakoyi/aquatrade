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

# 直接导入unified_engine
print("导入unified_engine...", flush=True)
t0 = time.time()
from core.backtest.unified_engine import UnifiedBacktestEngine
print(f"unified_engine: {time.time()-t0:.2f}s", flush=True)

print("完成", flush=True)
