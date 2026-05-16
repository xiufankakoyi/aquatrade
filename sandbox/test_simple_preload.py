"""
简单测试因子加载
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

from data_svc.unified_data_manager import get_unified_manager

print("=" * 60)
print("测试数据预加载")
print("=" * 60)

manager = get_unified_manager()
print(f"cache_loaded: {manager._cache_loaded}")

t0 = time.perf_counter()
manager.preload_to_memory(start_date='2024-01-01', end_date='2024-03-31')
elapsed = time.perf_counter() - t0

print(f"\n预加载耗时: {elapsed:.2f}s")
print(f"cache_loaded: {manager._cache_loaded}")

preloaded = manager.get_preloaded_data('2024-01-01', '2024-03-31')
stock_daily = preloaded.get('stock_daily')

if stock_daily is not None:
    print(f"\nstock_daily 行数: {len(stock_daily)}")
    print(f"stock_daily 列: {stock_daily.columns}")
    
    if 'ma5' in stock_daily.columns:
        sample = stock_daily.filter(stock_daily['trade_date'] == '2024-01-02').select(['stock_code', 'trade_date', 'close', 'ma5', 'ma10']).head(5)
        print(f"\n2024-01-02 样本:")
        print(sample)
    else:
        print("\nma5 列不存在!")
else:
    print("\nstock_daily 为空!")
