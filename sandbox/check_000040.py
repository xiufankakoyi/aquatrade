"""
检查000040的MA信号
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5

def check_000040():
    print("检查000040的MA信号...")
    
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2022-12-01",
        "2023-01-10",
        required_fields=['open', 'close'],
        use_adj_price=False
    )
    
    if matrix_data is None:
        print("❌ 加载失败")
        return
    
    matrices = matrix_data['matrices']
    dates = matrix_data['trading_dates']
    codes = matrix_data['stock_codes']
    
    # 找到000040的索引
    idx_000040 = None
    idx_000060 = None
    idx_000061 = None
    
    for i, code in enumerate(codes):
        if str(code) == '000040':
            idx_000040 = i
        elif str(code) == '000060':
            idx_000060 = i
        elif str(code) == '000061':
            idx_000061 = i
    
    print(f"\n000040 索引: {idx_000040}")
    print(f"000060 索引: {idx_000060}")
    print(f"000061 索引: {idx_000061}")
    
    if idx_000040 is not None:
        close_000040 = matrices['close'][:, idx_000040]
        
        print("\n000040 收盘价和MA:")
        for t, d in enumerate(dates):
            if t >= 10:
                ma5 = np.mean(close_000040[t-5:t])
                ma10 = np.mean(close_000040[t-10:t])
                ma5_prev = np.mean(close_000040[t-6:t-1])
                ma10_prev = np.mean(close_000040[t-11:t-1])
                
                # 金叉条件
                cross = ma5_prev <= ma10_prev and ma5 > ma10
                
                print(f"  {d}: close={close_000040[t]:.2f}, MA5={ma5:.2f}, MA10={ma10:.2f}, "
                      f"MA5_prev={ma5_prev:.2f}, MA10_prev={ma10_prev:.2f}, 金叉={cross}")
    
    if idx_000060 is not None:
        close_000060 = matrices['close'][:, idx_000060]
        
        print("\n000060 收盘价和MA:")
        for t, d in enumerate(dates):
            if t >= 10:
                ma5 = np.mean(close_000060[t-5:t])
                ma10 = np.mean(close_000060[t-10:t])
                ma5_prev = np.mean(close_000060[t-6:t-1])
                ma10_prev = np.mean(close_000060[t-11:t-1])
                
                cross = ma5_prev <= ma10_prev and ma5 > ma10
                
                print(f"  {d}: close={close_000060[t]:.2f}, MA5={ma5:.2f}, MA10={ma10:.2f}, "
                      f"MA5_prev={ma5_prev:.2f}, MA10_prev={ma10_prev:.2f}, 金叉={cross}")

if __name__ == "__main__":
    check_000040()
