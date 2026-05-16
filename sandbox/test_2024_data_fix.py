from pathlib import Path
import pandas as pd
import sys
sys.path.insert(0, str(Path('.').absolute()))

from data_svc.database.optimized_data_query_arcticdb import OptimizedStockDataQuery

# 测试查询 2024 年数据
query = OptimizedStockDataQuery(warmup=False)

# 测试获取交易日
dates = query.get_trading_dates("2024-01-01", "2024-12-31")
print(f"2024年交易日数量: {len(dates)}")
if dates:
    print(f"前5个交易日: {dates[:5]}")
    print(f"后5个交易日: {dates[-5:]}")

# 测试获取股票历史数据
print("\n测试获取 000001.SZ 的 2024 年数据...")
df = query.get_stock_history("000001.SZ", "2024-01-01", "2024-12-31", use_cache=False)
print(f"返回数据形状: {df.shape}")
if not df.empty:
    print(f"数据范围: {df.index.min()} ~ {df.index.max()}")
    print(f"2024年数据行数: {len(df)}")
    print(f"前3行:\n{df.head(3)}")
else:
    print("返回空数据!")
