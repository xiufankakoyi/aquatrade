"""
检查金叉股票排序
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
import polars as pl
from pathlib import Path

def check_golden_cross_order():
    print("检查金叉股票排序...")
    
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
    
    target_idx = dates.index('2023-01-03')
    
    # 获取股票过滤信息（不过滤ST）
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    new_codes = set(df_info.filter(pl.col('list_date') > 20221102)['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    close_prices = matrices['close']
    open_prices = matrices['open']
    
    golden_cross_stocks = []
    
    for i, code in enumerate(codes):
        code_str = str(code)
        
        if code_str in new_codes:
            continue
        
        t = target_idx
        if t < 11:
            continue
        
        close_col = close_prices[:, i]
        open_col = open_prices[:, i]
        
        if np.any(np.isnan(close_col[t-11:t])):
            continue
        if np.isnan(open_col[t]) or open_col[t] <= 0:
            continue
        
        ma5 = np.mean(close_col[t-5:t])
        ma10 = np.mean(close_col[t-10:t])
        ma5_prev = np.mean(close_col[t-6:t-1])
        ma10_prev = np.mean(close_col[t-11:t-1])
        
        if ma5_prev <= ma10_prev and ma5 > ma10:
            golden_cross_stocks.append({
                'code': code_str,
                'open': open_col[t],
            })
    
    # 按股票代码排序
    golden_cross_stocks.sort(key=lambda x: x['code'])
    
    print(f"\n金叉股票总数: {len(golden_cross_stocks)}")
    
    # 前10只
    print(f"\n前10只金叉股票（按代码排序）:")
    for i, s in enumerate(golden_cross_stocks[:10]):
        print(f"  {i+1}. {s['code']} 开盘价={s['open']:.2f}")
    
    # 聚宽买入的股票
    jq_buy = ['000021', '000039', '000040', '000049']
    print(f"\n聚宽买入的股票:")
    for code in jq_buy:
        idx = next((i for i, s in enumerate(golden_cross_stocks) if s['code'] == code), None)
        if idx is not None:
            print(f"  {code}: 排名第{idx+1}")
        else:
            print(f"  {code}: 不在列表中")

if __name__ == "__main__":
    check_golden_cross_order()
