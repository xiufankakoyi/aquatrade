"""
调试获取前一交易日
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_prev_date():
    print("=" * 80)
    print("检查获取前一交易日")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    
    for date in dates:
        print(f"\n当前日期: {date}")
        
        import pandas as pd
        from datetime import timedelta
        
        current = pd.to_datetime(date)
        for i in range(1, 10):
            prev = current - timedelta(days=i)
            prev_str = prev.strftime("%Y-%m-%d")
            df = data_query.get_stock_pool(prev_str)
            if df is not None and not df.empty:
                print(f"  前一交易日: {prev_str}, 数据行数: {len(df)}")
                break
            else:
                print(f"  {prev_str}: 无数据")


if __name__ == "__main__":
    check_prev_date()
