"""
详细检查000040的数据
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5

def check_000040_detail():
    print("详细检查000040的数据...")
    
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
    for i, code in enumerate(codes):
        if str(code) == '000040':
            idx_000040 = i
            break
    
    if idx_000040 is None:
        print("❌ 找不到000040")
        return
    
    close_col = matrices['close'][:, idx_000040]
    open_col = matrices['open'][:, idx_000040]
    
    print("\n000040 详细数据:")
    print(f"{'日期':<12} {'开盘':<10} {'收盘':<10} {'MA5':<10} {'MA10':<10} {'MA5_prev':<10} {'MA10_prev':<10} {'金叉':<6}")
    print("-" * 90)
    
    for t, d in enumerate(dates):
        if t < 11:
            continue
        
        ma5 = np.mean(close_col[t-5:t])
        ma10 = np.mean(close_col[t-10:t])
        ma5_prev = np.mean(close_col[t-6:t-1])
        ma10_prev = np.mean(close_col[t-11:t-1])
        
        cross = ma5_prev <= ma10_prev and ma5 > ma10
        
        print(f"{d:<12} {open_col[t]:<10.2f} {close_col[t]:<10.2f} {ma5:<10.4f} {ma10:<10.4f} {ma5_prev:<10.4f} {ma10_prev:<10.4f} {cross}")
    
    # 聚宽数据
    print("\n\n聚宽000040数据:")
    print("  2023-01-03 开盘价: 3.66")
    print("  我们的开盘价: {:.2f}".format(open_col[dates.index('2023-01-03')]))
    
    # 检查差异
    print("\n价格差异分析:")
    jq_open = 3.66
    our_open = open_col[dates.index('2023-01-03')]
    print(f"  聚宽开盘价: {jq_open}")
    print(f"  我们开盘价: {our_open:.2f}")
    print(f"  差异: {our_open - jq_open:.2f}")

if __name__ == "__main__":
    check_000040_detail()
