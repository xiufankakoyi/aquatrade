import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']
symbols = lib.list_symbols()[:100]

# 读取并过滤日期
start_date = '2024-01-01'
end_date = '2024-01-05'

dfs = []
for sym in symbols:
    try:
        result = lib.read(sym)
        data = result.data
        df = pl.from_pandas(data)
        
        # 过滤日期 - 和 unified_data_manager 一样
        if 'trade_date' in df.columns:
            df = df.filter(
                (pl.col('trade_date') >= pl.lit(start_date).str.to_date()) &
                (pl.col('trade_date') <= pl.lit(end_date).str.to_date())
            )
        
        if not df.is_empty():
            dfs.append(df)
    except Exception as e:
        pass

print(f"After date filter - dfs count: {len(dfs)}")
if dfs:
    print(f"First df shape: {dfs[0].shape}")
    print(f"First df columns: {dfs[0].columns}")
    print(f"First df ma5 sample: {dfs[0]['ma5'].head(3).to_list()}")
