"""
验证2025年股票价格是否合理
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def verify_2025_prices():
    print("=" * 80)
    print("验证2025年股票价格")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    test_stocks = ['600000', '603499', '603656']
    
    for code in test_stocks:
        print(f"\n{'='*60}")
        print(f"股票: {code}")
        print(f"{'='*60}")
        
        dates = ['2024-01-15', '2024-06-15', '2024-12-15', 
                 '2025-01-15', '2025-06-15', '2025-12-15']
        
        for date in dates:
            df = data_query.get_stock_pool(date)
            if df is not None:
                stock = df[df['stock_code'] == code]
                if not stock.empty:
                    row = stock.iloc[0]
                    print(f"  {date}: 开盘 {row.get('open', 0):.2f}, 收盘 {row.get('close', 0):.2f}")
    
    print("\n" + "=" * 80)
    print("检查是否有异常涨幅")
    print("=" * 80)
    
    for code in test_stocks:
        df_start = data_query.get_stock_pool('2024-01-02')
        df_end = data_query.get_stock_pool('2025-12-31')
        
        if df_start is not None and df_end is not None:
            start_data = df_start[df_start['stock_code'] == code]
            end_data = df_end[df_end['stock_code'] == code]
            
            if not start_data.empty and not end_data.empty:
                start_close = start_data.iloc[0].get('close', 0)
                end_close = end_data.iloc[0].get('close', 0)
                
                change = (end_close / start_close - 1) * 100 if start_close > 0 else 0
                print(f"\n{code}: 2024-01-02 收盘 {start_close:.2f} -> 2025-12-31 收盘 {end_close:.2f} = {change:.1f}%")


if __name__ == "__main__":
    verify_2025_prices()
