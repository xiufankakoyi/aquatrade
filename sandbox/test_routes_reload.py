import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')

# 直接测试 screener_routes 模块中的 get_latest_trade_date
import importlib
import server.routes.screener_routes as sr
importlib.reload(sr)

print("Testing get_latest_trade_date:")
result = sr.get_latest_trade_date()
print(f"Result: {result}")

print("\nTesting get_all_trade_dates:")
dates = sr.get_all_trade_dates()
print(f"First 3 dates: {dates[:3]}")