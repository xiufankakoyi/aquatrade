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

print("逐个测试导入...", flush=True)

tests = [
    ("datetime", "from datetime import datetime, date, timedelta"),
    ("typing", "from typing import Dict, Any, Generator, Tuple, List, Optional, Union, Callable"),
    ("dataclass", "from dataclasses import dataclass, field"),
    ("enum", "from enum import Enum"),
    ("pathlib", "from pathlib import Path"),
    ("lru_cache", "from functools import lru_cache"),
    ("logger", "from config.logger import get_logger"),
    ("Config", "from config.config import Config"),
]

for name, stmt in tests:
    t0 = time.time()
    exec(stmt)
    print(f"  {name}: {time.time()-t0:.2f}s", flush=True)

print("完成", flush=True)
