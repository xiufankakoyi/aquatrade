import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')

# 强制重新加载 screener_routes 模块
import importlib
from server.routes import screener_routes
importlib.reload(screener_routes)

print("screener_routes 模块已重新加载")

# 验证
from server.routes.screener_routes import get_latest_trade_date
print(f"最新日期: {get_latest_trade_date()}")