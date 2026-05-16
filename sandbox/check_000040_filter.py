"""
检查000040为什么被过滤掉
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
import polars as pl
from pathlib import Path

def check_000040_filter():
    print("检查000040为什么被过滤掉...")
    
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
    
    target_idx = dates.index('2023-01-03')
    close_col = matrices['close'][:, idx_000040]
    
    # 检查ST和次新股过滤
    info_path = Path("data/parquet_data/stock_info.parquet")
    df_info = pl.read_parquet(info_path)
    
    st_codes = set(df_info.filter(pl.col('is_st') == 1)['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    new_codes = set(df_info.filter(pl.col('list_date') > 20221102)['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    print(f"\n过滤检查:")
    print(f"  000040 in ST: {'000040' in st_codes}")
    print(f"  000040 in 次新股: {'000040' in new_codes}")
    
    # 检查数据有效性
    print(f"\n数据有效性检查:")
    print(f"  close_col[t-11:t] 范围: t-11={target_idx-11}, t={target_idx}")
    print(f"  对应日期: {dates[target_idx-11]} 到 {dates[target_idx-1]}")
    
    data_range = close_col[target_idx-11:target_idx]
    print(f"  数据值: {data_range}")
    print(f"  是否有NaN: {np.any(np.isnan(data_range))}")
    
    # 检查开盘价
    open_col = matrices['open'][:, idx_000040]
    print(f"\n开盘价检查:")
    print(f"  开盘价: {open_col[target_idx]}")
    print(f"  是否NaN: {np.isnan(open_col[target_idx])}")
    print(f"  是否<=0: {open_col[target_idx] <= 0}")

if __name__ == "__main__":
    check_000040_filter()
