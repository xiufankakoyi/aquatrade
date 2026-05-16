"""
深入检查回测引擎内部价格数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def inspect_stock_pool():
    print("=" * 80)
    print("检查股票池数据结构")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    dates = ['2024-09-30', '2024-10-08']
    problem_stocks = ['603499', '603656']
    
    for date in dates:
        print(f"\n{'='*60}")
        print(f"日期: {date}")
        print(f"{'='*60}")
        
        df = data_query.get_stock_pool(date)
        if df is None or df.empty:
            print("无数据")
            continue
        
        print(f"\n股票池列: {list(df.columns)}")
        
        for code in problem_stocks:
            stock_data = df[df['stock_code'] == code]
            if not stock_data.empty:
                row = stock_data.iloc[0]
                print(f"\n{code}:")
                for col in ['open', 'close', 'high', 'low', 'pct_chg', 'adj_factor', 'volume']:
                    if col in row:
                        print(f"  {col}: {row[col]}")
    
    print("\n" + "=" * 80)
    print("检查 data_dict 构建逻辑")
    print("=" * 80)
    
    df = data_query.get_stock_pool('2024-10-08')
    if df is not None and not df.empty:
        data_dict = df.set_index('stock_code').to_dict('index')
        
        for code in problem_stocks:
            if code in data_dict:
                print(f"\n{code} data_dict:")
                data = data_dict[code]
                print(f"  open: {data.get('open')}")
                print(f"  close: {data.get('close')}")
    
    print("\n" + "=" * 80)
    print("检查买入日期的价格")
    print("=" * 80)
    
    buy_dates = {
        '603499': '2024-09-13',
        '603656': '2024-10-18',
    }
    
    for code, buy_date in buy_dates.items():
        print(f"\n{code} 买入日期 {buy_date}:")
        df = data_query.get_stock_pool(buy_date)
        if df is not None:
            stock_data = df[df['stock_code'] == code]
            if not stock_data.empty:
                row = stock_data.iloc[0]
                print(f"  open: {row.get('open')}")
                print(f"  close: {row.get('close')}")


if __name__ == "__main__":
    inspect_stock_pool()
