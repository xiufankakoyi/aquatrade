import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']

# 读取单个股票 000001
item = lib.read('000001.SZ')
df = item.data

print(f"Columns: {df.columns.tolist()}")
print(f"\nma5 type: {df['ma5'].dtype}")
print(f"ma5 sample (Pandas): {df['ma5'].head(5).tolist()}")

# 转成 Polars 看看
import polars as pl
df_pl = pl.from_pandas(df)
print(f"\nma5 type (Polars): {df_pl['ma5'].dtype}")
print(f"ma5 sample (Polars): {df_pl['ma5'].head(5).to_list()}")
