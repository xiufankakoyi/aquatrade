"""
检查get_trading_dates返回的日期范围
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 70)
print("检查get_trading_dates返回的日期范围")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    # 获取2025-01-01到2025-01-31的交易日
    print(f"\n[2] 获取2025-01-01到2025-01-31的交易日...")
    trading_dates = data_query.get_trading_dates('2025-01-01', '2025-01-31')
    
    print(f"  交易日数量: {len(trading_dates)}")
    print(f"  开始日期: {trading_dates[0]}")
    print(f"  结束日期: {trading_dates[-1]}")
    print(f"\n  所有交易日:")
    for i, date in enumerate(trading_dates):
        print(f"    {i+1}. {date}")
    
    # 检查是否包含2025-01-20
    if '2025-01-20' in trading_dates:
        print(f"\n  ✓ 包含2025-01-20")
    else:
        print(f"\n  ✗ 不包含2025-01-20")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
