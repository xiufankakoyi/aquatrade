"""
检查 get_stock_pool 是否正确使用预加载数据
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_get_stock_pool():
    print("=" * 80)
    print("检查 get_stock_pool 是否正确使用预加载数据")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n预加载 {start_date} ~ {end_date}...")
    data_query.preload_backtest_data(start_date, end_date)
    
    # 检查预加载数据
    print(f"\n预加载数据状态:")
    print(f"  _preloaded_data 是否存在: {data_query._preloaded_data is not None}")
    if data_query._preloaded_data:
        print(f"  预加载日期数: {len(data_query._preloaded_data)}")
    
    # 测试 get_stock_pool
    print(f"\n测试 get_stock_pool('2024-01-02'):")
    result = data_query.get_stock_pool("2024-01-02")
    print(f"  返回行数: {len(result) if result is not None else 0}")
    print(f"  返回列: {list(result.columns) if result is not None else []}")
    
    # 检查预加载数据是否被使用
    print(f"\n检查预加载数据是否被使用:")
    preloaded_df = data_query.get_stock_pool_from_preloaded("2024-01-02")
    print(f"  get_stock_pool_from_preloaded 返回: {preloaded_df is not None}")
    if preloaded_df is not None:
        print(f"  预加载数据行数: {len(preloaded_df)}")

if __name__ == "__main__":
    check_get_stock_pool()
