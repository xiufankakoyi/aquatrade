"""
检查原始数据中 stock_code 的格式
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from datetime import datetime
from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic.get_library('stock_daily')

# 列出所有 symbols
symbols = list(lib.list_symbols())
print(f"Symbols: {symbols[:20]}")

if symbols:
    # 读取第一个 symbol 的数据
    df = lib.read(symbols[0]).data
    
    if df is not None:
        # 转换为 polars
        df_pl = pl.from_arrow(df)
        
        print(f"\n列名: {df_pl.columns}")
        print(f"\nstock_code 列示例:")
        print(df_pl['stock_code'].head(20))
        
        # 检查是否有前导零
        codes = df_pl['stock_code'].unique().sort().to_list()
        print(f"\n前20个代码: {codes[:20]}")
        print(f"后20个代码: {codes[-20:]}")
        
        # 检查是否有截断的代码
        truncated = [c for c in codes if len(str(c)) < 6]
        if truncated:
            print(f"\n截断的代码数量: {len(truncated)}")
            print(f"截断的代码示例: {truncated[:20]}")
