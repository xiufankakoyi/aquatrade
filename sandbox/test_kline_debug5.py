"""
调试测试：检查 ArcticDB 数据列名
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data_svc.unified_data_query import UnifiedDataQueryAdapter
import pandas as pd

# 创建查询适配器
adapter = UnifiedDataQueryAdapter()

# 获取数据
symbol_code = "603020"
df = adapter.get_stock_data(symbol_code, "2026-01-11", "2026-02-15")

print(f"[测试] ArcticDB 数据列名: {list(df.columns)}")
print(f"[测试] 数据形状: {df.shape}")
print(f"[测试] 索引名称: {df.index.name}")
print(f"[测试] 前3行数据:")
print(df.head(3))
