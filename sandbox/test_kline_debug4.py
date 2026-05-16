"""
调试测试：使用 BacktestVisualizationAPI
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from server.visualization_api import BacktestVisualizationAPI
import pandas as pd

api = BacktestVisualizationAPI()

symbol_code = "603020"
start_date = "2026-01-11"
end_date = "2026-02-15"

print(f"[测试] 查询 {symbol_code} 从 {start_date} 到 {end_date}")
print(f"[测试] api._initialized: {api._initialized}")
print(f"[测试] api.data_query type: {type(api.data_query)}")

# 手动调用初始化
api._ensure_initialized()
print(f"[测试] 初始化后 api._initialized: {api._initialized}")

# 标准化代码
normalized_code = api._normalize_symbol_code(symbol_code)
print(f"[测试] 标准化后的代码: {normalized_code}")

# 直接查询数据
history_df = api.data_query.get_stock_history(
    normalized_code, start_date, end_date,
    columns=["stock_code", "trade_date", "open", "high", "low", "close", "volume", "adj_factor", "ma5", "ma10", "ma20"]
)

print(f"[测试] 查询结果:")
print(f"  - history_df is None: {history_df is None}")
if history_df is not None:
    print(f"  - history_df.empty: {history_df.empty}")
    print(f"  - history_df.shape: {history_df.shape}")
    if not history_df.empty:
        print(f"  - 第一行数据:")
        print(history_df.iloc[0])

# 获取全局最新因子
base_factor = api._get_global_latest_factor(normalized_code)
print(f"[测试] 全局最新因子: {base_factor}")

# 现在调用完整的 API
result = api.get_symbol_kline(symbol_code, start_date, end_date)
print(f"[测试] API 返回 {len(result)} 条数据")
if result:
    print(f"[测试] 第一条: {result[0]}")
