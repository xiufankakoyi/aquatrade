import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']
symbols = lib.list_symbols()[:3]

for sym in symbols:
    item = lib.read(sym)
    data = item.data
    
    # 重置索引
    data = data.reset_index()
    df = pl.from_pandas(data)
    
    print(f"\n{sym}:")
    print(f"  date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
    print(f"  total rows: {len(df)}")
    print(f"  ma5 null_count: {df['ma5'].null_count()}")
    print(f"  ma5 sample (first 5): {df['ma5'].head(5).to_list()}")
    print(f"  ma5 sample (last 5): {df['ma5'].tail(5).to_list()}")
