import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.unified_data_manager import get_unified_manager

mgr = get_unified_manager()

result = mgr.read('stock_daily', start_date='2024-01-01', end_date='2024-01-05')
print(f"Columns: {result.columns}")

if 'ma5' in result.columns:
    print(f"\nma5 sample: {result['ma5'].head(3).to_list()}")
