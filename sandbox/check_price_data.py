"""
检查000001的价格数据，对比聚宽和AquaTrade的差异
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import UnifiedDataManager
import pandas as pd

print("=" * 70)
print("检查000001价格数据")
print("=" * 70)

data_mgr = UnifiedDataManager()

# 获取2025-01-21和2025-01-24的数据
dates = ['2025-01-21', '2025-01-24']

for date in dates:
    print(f"\n【{date}】")
    df = data_mgr.read('stock_daily', start_date=date, end_date=date, symbol='000001')
    print(f"  数据类型: {type(df)}")
    if df is not None:
        if isinstance(df, pd.DataFrame):
            print(f"  数据形状: {df.shape}")
            if not df.empty:
                print(f"  数据列: {list(df.columns)}")
                row = df.iloc[0]
                print(f"  开盘价(open): {row.get('open', 'N/A')}")
                print(f"  收盘价(close): {row.get('close', 'N/A')}")
                print(f"  最高价(high): {row.get('high', 'N/A')}")
                print(f"  最低价(low): {row.get('low', 'N/A')}")
                print(f"  复权因子(adj_factor): {row.get('adj_factor', 'N/A')}")
        else:
            print(f"  数据: {df}")
    else:
        print("  无数据")

print("\n" + "=" * 70)
print("聚宽日志中的价格:")
print("=" * 70)
print("2025-01-21: 开盘价11.46 (买入价)")
print("2025-01-24: 开盘价11.32，但卖出成交价为11.31")
print("\n注意：聚宽卖出时显示 'trade price: 11.31'，但开盘价是11.32")
print("这可能是滑点或市场冲击导致的")

print("\n" + "=" * 70)
print("可能的原因:")
print("=" * 70)
print("1. 数据源不同：聚宽使用自己的行情，AquaTrade使用Tushare")
print("2. 复权因子计算差异")
print("3. 聚宽卖出时使用了滑点或市场冲击模型")
print("4. 价格精度舍入差异")
