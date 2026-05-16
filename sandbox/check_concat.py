import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']
symbols = lib.list_symbols()

# 读取前5个，转成 Polars 再 concat
dfs = []
for s in symbols[:5]:
    item = lib.read(s)
    df = item.data
    # 转成 Polars
    df = pl.from_pandas(df)
    dfs.append(df)

# 使用 diagonal concat
combined = pl.concat(dfs, how='diagonal')
print(f"Combined columns ({len(combined.columns)}): {combined.columns}")
print(f"ma5 in columns: {'ma5' in combined.columns}")
if 'ma5' in combined.columns:
    print(f"ma5 sample: {combined['ma5'].head(3).to_list()}")
