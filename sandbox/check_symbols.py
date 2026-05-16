import os
os.environ['DB_BACKEND'] = 'arcticdb'

from data_svc.unified_data_manager import get_unified_manager
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library

arctic = get_arctic_instance_for_library('stock_daily')
lib = arctic['stock_daily']

# 检查 symbols
symbols = lib.list_symbols()
print(f"Total symbols: {len(symbols)}")

# 读取前3个，检查列
all_cols = set()
for s in symbols[:5]:
    item = lib.read(s)
    df = item.data
    print(f"\n{s}:")
    print(f"  Columns ({len(df.columns)}): {df.columns[:10]}...")
    all_cols.update(df.columns)

print(f"\n合并后所有列: {sorted(all_cols)}")
