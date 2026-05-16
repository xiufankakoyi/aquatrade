"""
检查2025-01-01是否是交易日
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import pandas as pd

query = OptimizedStockDataQuery()

print("=" * 60)
print("检查2025-01-01是否是交易日")
print("=" * 60)

# 获取交易日列表
trading_dates = query.get_trading_dates('2024-12-25', '2025-01-10')
print(f"\n交易日列表: {trading_dates}")
print(f"\n2025-01-01是否是交易日: {'2025-01-01' in trading_dates}")

# 检查2024-12-31（前一天）
print(f"\n2024-12-31是否是交易日: {'2024-12-31' in trading_dates}")

# 如果2025-01-01不是交易日，那么2025-01-02的信号应该基于2024-12-31
if '2025-01-01' not in trading_dates and '2024-12-31' in trading_dates:
    print("\n结论:")
    print("  2025-01-01不是交易日（元旦假期）")
    print("  2025-01-02的信号应该基于2024-12-31的数据")
    print("  但当前数据预加载可能没有包含2024-12-31")

# 直接查询2024-12-31的数据
print("\n" + "=" * 60)
print("查询2024-12-31的数据")
print("=" * 60)

try:
    from data_svc.unified_data_manager import get_unified_manager
    manager = get_unified_manager()
    
    df = manager.read('stock_daily', start_date='2024-12-31', end_date='2024-12-31')
    if df is not None and not df.is_empty():
        print(f"2024-12-31有 {len(df)} 条数据")
        print(f"股票数量: {df['stock_code'].n_unique()}")
    else:
        print("2024-12-31没有数据")
except Exception as e:
    print(f"查询失败: {e}")
