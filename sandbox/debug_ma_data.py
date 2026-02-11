# debug_ma_data.py

import pandas as pd
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def inspect_data():
    target_code = "601988.XSHG"
    start_date = "2023-10-01"
    end_date = "2024-12-31"
    
    dq = OptimizedStockDataQuery()
    hist = dq.get_batch_stock_history([target_code], start_date, end_date)
    
    if hist.empty:
        print("未找到数据。")
        return
        
    hist = hist.sort_values('trade_date')
    hist['ma5'] = hist['close'].rolling(window=5).mean()
    hist['ma10'] = hist['close'].rolling(window=10).mean()
    
    # 查找金叉/死叉
    hist['ma5_prev'] = hist['ma5'].shift(1)
    hist['ma10_prev'] = hist['ma10'].shift(1)
    
    golden = (hist['ma5_prev'] <= hist['ma10_prev']) & (hist['ma5'] > hist['ma10'])
    death = (hist['ma5_prev'] >= hist['ma10_prev']) & (hist['ma5'] < hist['ma10'])
    
    print(f"数据总行数: {len(hist)}")
    print(f"金叉天数: {golden.sum()}")
    print(f"死叉天数: {death.sum()}")
    
    if golden.sum() > 0:
        print("\n金叉发生日期:")
        print(hist[golden][['trade_date', 'close', 'ma5', 'ma10']])
        
    if death.sum() > 0:
        print("\n死叉发生日期:")
        print(hist[death][['trade_date', 'close', 'ma5', 'ma10']])

if __name__ == "__main__":
    inspect_data()
