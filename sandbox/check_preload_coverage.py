"""
检查策略内部查询的日期是否在预加载范围内
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_preload_coverage():
    print("=" * 80)
    print("检查预加载数据覆盖范围")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n预加载 {start_date} ~ {end_date}...")
    data_query.preload_backtest_data(start_date, end_date)
    
    # 检查预加载日期范围
    print(f"\n预加载日期范围: {data_query._preloaded_date_range}")
    
    # 检查预加载数据包含的日期
    if data_query._preloaded_data:
        print(f"\n预加载数据包含的日期:")
        for date in sorted(data_query._preloaded_data.keys()):
            print(f"  {date}")
    
    # 测试策略需要的日期
    print(f"\n测试策略需要的日期:")
    test_dates = [
        "2023-12-29",  # 前一交易日
        "2024-01-01",  # 非交易日
        "2024-01-02",  # 第一个交易日
        "2024-01-03",
    ]
    
    for date in test_dates:
        preloaded = data_query.get_stock_pool_from_preloaded(date)
        print(f"  {date}: {'在预加载中' if preloaded is not None else '不在预加载中'}")

if __name__ == "__main__":
    check_preload_coverage()
