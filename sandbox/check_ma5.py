import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']
symbols = lib.list_symbols()

# 检查前几个 symbol 的 ma5 列
for s in symbols[:10]:
    item = lib.read(s)
    df = item.data
    has_ma5 = 'ma5' in df.columns
    ma5_vals = df['ma5'].head(3).tolist() if has_ma5 else None
    print(f"{s}: ma5 exists={has_ma5}, values={ma5_vals}")
