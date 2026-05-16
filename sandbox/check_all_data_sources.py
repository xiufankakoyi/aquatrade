"""
检查所有数据源
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from data_svc.storage.arcticdb_manager import get_arctic_instance

# 检查 ArcticDB
arctic = get_arctic_instance()
libs = arctic.list_libraries()
print("=" * 60)
print("ArcticDB 库:")
print("=" * 60)

for lib_name in libs:
    lib = arctic.get_library(lib_name)
    symbols = list(lib.list_symbols())
    print(f"{lib_name}: {len(symbols)} 个 symbols")
    if symbols:
        print(f"  示例: {symbols[:3]}")

# 检查 Parquet 目录
print("\n" + "=" * 60)
print("Parquet 文件:")
print("=" * 60)

parquet_dirs = [
    './data/parquet',
    './data',
]

for pdir in parquet_dirs:
    full_path = Path(project_root) / pdir
    if full_path.exists():
        files = list(full_path.glob('*.parquet'))
        print(f"{pdir}: {len(files)} 个文件")
        if files:
            print(f"  示例: {[f.name for f in files[:3]]}")
    else:
        print(f"{pdir}: 不存在")

# 检查数据库
print("\n" + "=" * 60)
print("SQLite 数据库:")
print("=" * 60)

db_path = Path(project_root) / 'data' / 'database' / 'stock_data.db'
if db_path.exists():
    print(f"数据库存在: {db_path}")
    print(f"大小: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
else:
    print("数据库不存在")
