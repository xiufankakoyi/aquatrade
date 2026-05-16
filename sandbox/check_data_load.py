"""
检查数据加载情况
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic.get_library('stock_daily')

# 列出所有 symbols
symbols = list(lib.list_symbols())
print(f"Symbols 数量: {len(symbols)}")
print(f"前10个: {symbols[:10]}")

if symbols:
    # 读取第一个 symbol 的数据
    df = lib.read(symbols[0]).data
    df_pl = pl.from_arrow(df)
    
    print(f"\n列名: {df_pl.columns}")
    print(f"行数: {len(df_pl)}")
    
    # 检查日期范围
    dates = df_pl['trade_date'].unique().sort().to_list()
    print(f"\n日期范围: {dates[0]} 到 {dates[-1]}")
    print(f"交易日数: {len(dates)}")
