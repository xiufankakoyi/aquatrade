"""
强制重新加载 API 模块（用于开发调试）
"""
import sys

# 清除缓存的模块
modules_to_remove = [
    'server.visualization_api',
    'server.app',
    'server.routes.data_routes',
]

for mod in modules_to_remove:
    if mod in sys.modules:
        del sys.modules[mod]
        print(f"Removed cached module: {mod}")

# 重新导入
from server.app import get_api

# 重置全局 api 实例
import server.app as app_module
app_module.api = None

# 重新获取 API 实例
api = get_api()

# 测试
try:
    result = api._get_index_kline_from_parquet('000300', '2024-01-01', '2024-12-31')
    print(f"\nTest result: {len(result)} records")
    if result:
        print(f"First: {result[0]}")
except Exception as e:
    print(f"Error: {e}")
