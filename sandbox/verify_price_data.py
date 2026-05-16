"""
验证 2024-10-08 前后的实际行情数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def verify_price_data():
    print("=" * 80)
    print("验证 2024-10-08 前后的实际行情数据")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    problem_stocks = ['603499', '601929', '600449', '603656', '600629']
    
    print("\n【检查 2024-10-08 当日数据】")
    df_1008 = data_query.get_stock_pool('2024-10-08')
    if df_1008 is not None:
        for code in problem_stocks:
            stock_data = df_1008[df_1008['stock_code'] == code]
            if not stock_data.empty:
                row = stock_data.iloc[0]
                close = row.get('close', 0)
                pct_chg = row.get('pct_chg', 0)
                print(f"\n{code} @ 2024-10-08:")
                print(f"  收盘: {close}, 涨跌幅: {pct_chg}%")
    
    print("\n【检查 2024-09-30 节前最后一天】")
    df_0930 = data_query.get_stock_pool('2024-09-30')
    if df_0930 is not None:
        for code in problem_stocks:
            stock_data = df_0930[df_0930['stock_code'] == code]
            if not stock_data.empty:
                row = stock_data.iloc[0]
                close = row.get('close', 0)
                print(f"\n{code} @ 2024-09-30:")
                print(f"  收盘: {close}")
    
    print("\n【计算实际涨跌幅】")
    if df_1008 is not None and df_0930 is not None:
        for code in problem_stocks:
            stock_1008 = df_1008[df_1008['stock_code'] == code]
            stock_0930 = df_0930[df_0930['stock_code'] == code]
            
            if not stock_1008.empty and not stock_0930.empty:
                close_1008 = stock_1008.iloc[0].get('close', 0)
                close_0930 = stock_0930.iloc[0].get('close', 0)
                
                if close_0930 > 0:
                    actual_change = (close_1008 / close_0930 - 1) * 100
                    print(f"{code}: 09-30收盘 {close_0930:.2f} -> 10-08收盘 {close_1008:.2f} = {actual_change:.1f}%")
    
    print("\n" + "=" * 80)
    print("【检查历史数据】")
    print("=" * 80)
    
    for code in problem_stocks[:3]:
        print(f"\n{code} 历史数据:")
        df_hist = data_query.get_stock_history(code, '2024-09-27', '2024-10-10')
        if df_hist is not None and not df_hist.empty:
            print(df_hist[['trade_date', 'open', 'close', 'high', 'low', 'pct_chg']].to_string())
        else:
            print("  无数据")


if __name__ == "__main__":
    verify_price_data()
