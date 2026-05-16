import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']

symbols = lib.list_symbols()
print(f"Total symbols: {len(symbols)}")
print(f"First 10: {symbols[:10]}")

# 检查前几个是什么类型
for s in symbols[:3]:
    item = lib.read(s)
    df = item.data
    print(f"\n{s}: shape={df.shape}, columns count={len(df.columns)}")
