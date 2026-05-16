"""
检查2023-01-03的金叉信号股票列表
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
import polars as pl
from pathlib import Path

def check_golden_cross():
    print("检查2023-01-03的金叉信号...")
    
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
    T = len(dates)
    
    # 找到2023-01-03的索引
    target_idx = dates.index('2023-01-03')
    print(f"2023-01-03 索引: {target_idx}")
    
    # 获取股票过滤信息
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    
    st_codes = set(df_info.filter(pl.col('is_st') == 1)['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    new_codes = set(df_info.filter(pl.col('list_date') > 20221102)['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    print(f"\nST股票: {len(st_codes)} 只")
    print(f"次新股: {len(new_codes)} 只")
    
    # 找出所有金叉股票
    close_prices = matrices['close']
    open_prices = matrices['open']
    
    golden_cross_stocks = []
    
    for i, code in enumerate(codes):
        code_str = str(code)
        
        # 过滤ST和次新股
        if code_str in st_codes or code_str in new_codes:
            continue
        
        # 检查金叉条件
        t = target_idx
        if t < 11:
            continue
        
        close_col = close_prices[:, i]
        open_col = open_prices[:, i]
        
        # 检查数据有效性
        if np.any(np.isnan(close_col[t-11:t])):
            continue
        if np.isnan(open_col[t]) or open_col[t] <= 0:
            continue
        
        # 计算MA
        ma5 = np.mean(close_col[t-5:t])
        ma10 = np.mean(close_col[t-10:t])
        ma5_prev = np.mean(close_col[t-6:t-1])
        ma10_prev = np.mean(close_col[t-11:t-1])
        
        # 金叉条件
        if ma5_prev <= ma10_prev and ma5 > ma10:
            golden_cross_stocks.append({
                'code': code_str,
                'open': open_col[t],
                'ma5': ma5,
                'ma10': ma10,
                'ma5_prev': ma5_prev,
                'ma10_prev': ma10_prev
            })
    
    # 按股票代码排序
    golden_cross_stocks.sort(key=lambda x: x['code'])
    
    print(f"\n2023-01-03 金叉股票数量: {len(golden_cross_stocks)}")
    print(f"\n前20只金叉股票（按代码排序）:")
    print(f"{'代码':<10} {'开盘价':<10} {'MA5':<10} {'MA10':<10}")
    print("-" * 50)
    for s in golden_cross_stocks[:20]:
        print(f"{s['code']:<10} {s['open']:<10.2f} {s['ma5']:<10.2f} {s['ma10']:<10.2f}")
    
    # 检查聚宽买入的股票是否在列表中
    jq_buy = ['000021', '000039', '000040', '000049']
    print(f"\n聚宽买入的股票:")
    for code in jq_buy:
        found = next((s for s in golden_cross_stocks if s['code'] == code), None)
        if found:
            print(f"  {code}: 在列表中, 开盘价={found['open']:.2f}")
        else:
            print(f"  {code}: 不在列表中")

if __name__ == "__main__":
    check_golden_cross()
