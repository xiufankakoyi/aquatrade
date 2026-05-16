"""
简单测试：直接查询 K 线数据
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from server.visualization_api import BacktestVisualizationAPI

api = BacktestVisualizationAPI()

# 测试查询
symbol_code = "603020"
start_date = "2026-01-11"
end_date = "2026-02-15"

print(f"[测试] 查询 {symbol_code} 从 {start_date} 到 {end_date}")

result = api.get_symbol_kline(symbol_code, start_date, end_date)

print(f"[测试] 返回 {len(result)} 条数据")
if result:
    print(f"[测试] 第一条: {result[0]}")
    print(f"[测试] 最后一条: {result[-1]}")
else:
    print("[测试] 数据为空!")
