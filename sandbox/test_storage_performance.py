"""
性能测试：对比 daily 库（分开存储）vs stock_daily 库（合并存储 + 内存缓存）
"""
import time
import random
import logging
import sys

logging.disable(logging.CRITICAL)

from data_svc.storage.arcticdb_manager import get_arctic_instance
from data_svc.unified_data_manager import get_unified_manager
import polars as pl

arctic = get_arctic_instance()

daily_lib = arctic['daily']
stock_daily_lib = arctic['stock_daily']

daily_symbols = daily_lib.list_symbols()
test_codes = random.sample(daily_symbols, min(10, len(daily_symbols)))
test_codes_pure = [s.split('.')[0] for s in test_codes]

print(f'测试股票数: {len(test_codes)}')
print(f'测试代码: {test_codes_pure[:5]}...')
sys.stdout.flush()

print('\n=== 测试 1: daily 库（分开存储）===')
sys.stdout.flush()
daily_times = []
for i in range(100):
    code = random.choice(test_codes)
    start = time.perf_counter()
    data = daily_lib.read(code)
    df = data.data
    elapsed = (time.perf_counter() - start) * 1000
    daily_times.append(elapsed)

print(f'  平均耗时: {sum(daily_times)/len(daily_times):.2f} ms')
print(f'  最小耗时: {min(daily_times):.2f} ms')
print(f'  最大耗时: {max(daily_times):.2f} ms')
print(f'  P95 耗时: {sorted(daily_times)[int(len(daily_times)*0.95)]:.2f} ms')
sys.stdout.flush()

print('\n=== 测试 2: stock_daily 库（合并存储 + 内存缓存）===')
sys.stdout.flush()

manager = get_unified_manager()

print('  预热缓存...')
sys.stdout.flush()
warmup_start = time.perf_counter()
manager.preload_to_memory(start_date='2024-01-01', end_date='2024-12-31')
warmup_elapsed = (time.perf_counter() - warmup_start) * 1000
print(f'  预热耗时: {warmup_elapsed:.2f} ms')
sys.stdout.flush()

stock_daily_times = []
for i in range(100):
    code = random.choice(test_codes_pure)
    start = time.perf_counter()
    
    df = manager.read('stock_daily', start_date='2024-01-01', end_date='2024-12-31', use_cache=True)
    
    if 'stock_code' in df.columns:
        filtered = df.filter(pl.col('stock_code') == code)
    else:
        filtered = df
    
    elapsed = (time.perf_counter() - start) * 1000
    stock_daily_times.append(elapsed)

print(f'  平均耗时: {sum(stock_daily_times)/len(stock_daily_times):.2f} ms')
print(f'  最小耗时: {min(stock_daily_times):.2f} ms')
print(f'  最大耗时: {max(stock_daily_times):.2f} ms')
print(f'  P95 耗时: {sorted(stock_daily_times)[int(len(stock_daily_times)*0.95)]:.2f} ms')
sys.stdout.flush()

print('\n=== 性能对比 ===')
sys.stdout.flush()
avg_daily = sum(daily_times)/len(daily_times)
avg_stock_daily = sum(stock_daily_times)/len(stock_daily_times)
diff = avg_stock_daily - avg_daily

print(f'  daily 库平均: {avg_daily:.2f} ms')
print(f'  stock_daily 库平均 (缓存): {avg_stock_daily:.2f} ms')
print(f'  差异: {diff:.2f} ms ({diff/avg_daily*100:.1f}%)')
sys.stdout.flush()

if abs(diff) < 100:
    print(f'\n✅ 性能差距在可接受范围内 (< 100ms)，可以安全合并')
else:
    print(f'\n⚠️ 性能差距较大 (> 100ms)，建议保留分开存储')
sys.stdout.flush()
