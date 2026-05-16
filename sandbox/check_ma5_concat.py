import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']
symbols = lib.list_symbols()[:20]

# 模拟 unified_data_manager.read() 的处理
dfs = []
for sym in symbols:
    try:
        result = lib.read(sym)
        data = result.data
        df = pl.from_pandas(data)
        dfs.append(df)
    except:
        pass

print(f"Before concat - first df ma5: {dfs[0]['ma5'].head(3).to_list()}")

# 检查类型
print(f"\nBefore concat - first df schema:")
print(dfs[0].schema)

# 做 integer 列转换
all_dfs_normalized = []
for d in dfs:
    int_cols = [
        c for c in d.columns
        if d.schema[c] in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64]
    ]
    if int_cols:
        print(f"Converting int cols: {int_cols}")
        d = d.with_columns([
            pl.col(c).cast(pl.Float64) for c in int_cols
        ])
    all_dfs_normalized.append(d)

# concat
combined = pl.concat(all_dfs_normalized, how='diagonal')
print(f"\nAfter concat - ma5 sample: {combined['ma5'].head(3).to_list()}")
print(f"After concat - schema: {combined.schema}")
