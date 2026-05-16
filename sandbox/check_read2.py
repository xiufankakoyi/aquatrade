import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.unified_data_manager import get_unified_manager

mgr = get_unified_manager()

# 用短时间测试
df = mgr.read('stock_daily', start_date='2026-01-01', end_date='2026-01-15', use_cache=False)

print(f"read() result: {len(df)} rows")
print(f"Columns: {len(df.columns)}")
print(f"Has ma5: {'ma5' in df.columns}")
if 'ma5' in df.columns:
    print(f"ma5 null_count: {df['ma5'].null_count()}")
    print(f"ma5 sample: {df['ma5'].head(10).to_list()}")
