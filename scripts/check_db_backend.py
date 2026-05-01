#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断脚本：检查数据库后端配置"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("数据库后端诊断工具")
print("=" * 60)

# 1. 检查环境变量
print("\n[1] 检查环境变量 DB_BACKEND:")
db_backend = os.getenv("DB_BACKEND", "arcticdb")
print(f"   当前值: {db_backend}")

# 2. 检查 ArcticDB 是否安装
print("\n[2] 检查 ArcticDB 包:")
try:
    import arcticdb
    print(f"   [OK] arcticdb installed (version: {getattr(arcticdb, '__version__', 'unknown')})")
    arcticdb_available = True
except ImportError as e:
    print(f"   [FAIL] arcticdb not installed: {e}")
    arcticdb_available = False

# 3. 检查 Polars 是否安装
print("\n[3] 检查 Polars 包:")
try:
    import polars
    print(f"   [OK] polars installed (version: {getattr(polars, '__version__', 'unknown')})")
    polars_available = True
except ImportError as e:
    print(f"   [FAIL] polars not installed: {e}")
    polars_available = False

# 4. 检查 PyArrow 是否安装
print("\n[4] 检查 PyArrow 包:")
try:
    import pyarrow
    print(f"   [OK] pyarrow installed (version: {getattr(pyarrow, '__version__', 'unknown')})")
    pyarrow_available = True
except ImportError as e:
    print(f"   [FAIL] pyarrow not installed: {e}")
    pyarrow_available = False

# 5. 检查 ArcticDB 数据目录
print("\n[5] 检查 ArcticDB 数据目录:")
try:
    from config.config import Config
    arctic_path = getattr(Config, 'ARCTICDB_PATH', 'data/arctic_db')
    print(f"   目录路径: {arctic_path}")
    print(f"   目录存在: {Path(arctic_path).exists()}")
except Exception as e:
    print(f"   [FAIL] Check failed: {e}")

# 6. 尝试初始化 ArcticDBManager
print("\n[6] 尝试初始化 ArcticDBManager:")
if arcticdb_available:
    try:
        from data_svc.storage.arcticdb_manager import get_arcticdb_manager
        manager = get_arcticdb_manager()
        print("   [OK] ArcticDBManager initialized successfully")
        
        libraries = manager.list_libraries()
        print(f"   已有库: {libraries}")
    except Exception as e:
        print(f"   [FAIL] ArcticDBManager init failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("   Skipped (arcticdb not installed)")

# 7. 检查架构配置
print("\n[7] 当前架构配置:")
backend = os.getenv("DB_BACKEND", "arcticdb").lower()
print(f"   DB_BACKEND: {backend}")
if backend == "arcticdb":
    print("   → 使用 ArcticDB + Polars 两层架构")
elif backend == "parquet":
    print("   → 使用 Parquet 文件存储")
else:
    print(f"   → 未知后端: {backend}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
