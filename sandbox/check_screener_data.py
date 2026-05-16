import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.unified_data_manager import get_unified_manager

manager = get_unified_manager()
print(f"Cache loaded: {manager._cache_loaded}")
print(f"Memory cache keys: {list(manager._memory_cache.keys())}")

if 'stock_daily' in manager._memory_cache:
    print(f"stock_daily cache keys: {list(manager._memory_cache['stock_daily'].keys())}")
    for key, df in manager._memory_cache['stock_daily'].items():
        print(f"  {key}: shape={df.shape}, columns={list(df.columns)[:10]}")
        if 'trade_date' in df.columns:
            dates = df['trade_date'].unique().to_list()[:5]
            print(f"    Sample dates: {dates}")
        else:
            print(f"    No trade_date column!")
else:
    print("No stock_daily in memory cache!")
