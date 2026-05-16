import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.unified_data_manager import get_unified_manager

mgr = get_unified_manager()
mgr.preload_to_memory(years=3)

# 直接检查 stock_daily 的 ma5
for lib_name, cache in mgr._memory_cache.items():
    for key, df in cache.items():
        if lib_name == 'stock_daily':
            # 直接看 ma5 的值
            print(f"ma5 dtype: {df.schema['ma5']}")
            print(f"ma5 null_count: {df['ma5'].null_count()}")
            print(f"ma5 sample: {df['ma5'].head(20).to_list()}")
            
            # 检查有值的
            ma5_valid = df.filter(pl.col('ma5').is_not_null())
            print(f"\nValid ma5 rows: {len(ma5_valid)}")
            if len(ma5_valid) > 0:
                print(ma5_valid.select(['trade_date', 'stock_code', 'close', 'ma5']).head(5))
