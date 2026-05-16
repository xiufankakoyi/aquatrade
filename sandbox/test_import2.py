import time
print("开始", flush=True)

t0 = time.time()
import numpy as np
print(f"numpy: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
import pandas as pd
print(f"pandas: {time.time()-t0:.2f}s", flush=True)

print("\n=== 逐个导入 ===", flush=True)

t0 = time.time()
import sys
sys.path.insert(0, '.')
from config.logger import get_logger
print(f"logger: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
from config.config import Config
print(f"config: {time.time()-t0:.2f}s", flush=True)

print("\n完成", flush=True)
