"""
调试测试：查看数据结构
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from server.services.data_initialization_service import DataInitializationService

init_service = DataInitializationService()
init_service.ensure_initialized()

symbol_code = "603020"
start_date = "2026-01-11"
end_date = "2026-02-15"

print(f"[测试] 查询 {symbol_code} 从 {start_date} 到 {end_date}")

# 直接查询数据
history_df = init_service.data_query.get_stock_history(
    symbol_code, start_date, end_date,
    columns=["stock_code", "trade_date", "open", "high", "low", "close", "volume", "adj_factor", "ma5", "ma10", "ma20"]
)

print(f"[测试] 查询结果:")
print(f"  - history_df is None: {history_df is None}")
if history_df is not None:
    print(f"  - history_df.empty: {history_df.empty}")
    print(f"  - history_df.shape: {history_df.shape}")
    print(f"  - history_df.columns: {list(history_df.columns)}")
    if not history_df.empty:
        print(f"  - 第一行数据:")
        print(history_df.iloc[0])
        print(f"  - 数据类型:")
        print(history_df.dtypes)
