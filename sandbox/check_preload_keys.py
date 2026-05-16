"""
检查预加载数据的 key 格式
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_preload_keys():
    print("=" * 80)
    print("检查预加载数据的 key 格式")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n预加载 {start_date} ~ {end_date}...")
    data_query.preload_backtest_data(start_date, end_date)
    
    preloaded = data_query._preloaded_data
    if preloaded:
        print(f"\n预加载数据 keys ({len(preloaded)} 个):")
        for key in list(preloaded.keys())[:10]:
            print(f"  '{key}' (type: {type(key).__name__})")
        
        print(f"\n尝试获取 2024-01-02:")
        result = data_query.get_stock_pool_from_preloaded("2024-01-02")
        print(f"  结果: {result is not None}")
        
        print(f"\n尝试获取 2024-01-03:")
        result = data_query.get_stock_pool_from_preloaded("2024-01-03")
        print(f"  结果: {result is not None}")
    else:
        print("预加载数据为空")

if __name__ == "__main__":
    check_preload_keys()
