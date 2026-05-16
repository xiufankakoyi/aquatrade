"""
检查预加载数据的列是否完整
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_preload_columns():
    print("=" * 80)
    print("检查预加载数据的列")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n预加载 {start_date} ~ {end_date}...")
    data_query.preload_backtest_data(start_date, end_date)
    
    preloaded = data_query._preloaded_data
    if preloaded:
        first_key = list(preloaded.keys())[0]
        df = preloaded[first_key]
        print(f"\n预加载数据列 ({first_key}):")
        print(f"  列数: {len(df.columns)}")
        print(f"  列名: {list(df.columns)}")
        
        # 检查关键列
        required_cols = ['stock_code', 'close', 'open', 'adj_factor', 'total_mv', 
                         'is_suspended', 'is_limit_up', 'is_limit_down']
        print(f"\n关键列检查:")
        for col in required_cols:
            exists = col in df.columns
            print(f"  {col}: {'✓' if exists else '✗'}")
        
        # 测试 get_stock_pool_from_preloaded
        print(f"\n测试 get_stock_pool_from_preloaded:")
        result = data_query.get_stock_pool_from_preloaded("2024-01-02")
        if result is not None:
            print(f"  返回列: {list(result.columns)}")
        else:
            print("  返回 None")
    else:
        print("预加载数据为空")

if __name__ == "__main__":
    check_preload_columns()
