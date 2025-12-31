#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断脚本：检查为什么系统使用 SQLite 而不是 LanceDB"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("数据库后端诊断工具")
print("=" * 60)

# 1. 检查环境变量
print("\n[1] 检查环境变量 DB_BACKEND:")
db_backend = os.getenv("DB_BACKEND", "NOT SET")
print(f"   当前值: {db_backend}")

# 2. 检查 lancedb 是否安装
print("\n[2] 检查 lancedb 包:")
try:
    import lancedb
    print(f"   [OK] lancedb installed (version: {getattr(lancedb, '__version__', 'unknown')})")
    lancedb_available = True
except ImportError as e:
    print(f"   [FAIL] lancedb not installed: {e}")
    lancedb_available = False

# 3. 检查 pyarrow 是否安装
print("\n[3] 检查 pyarrow 包:")
try:
    import pyarrow
    print(f"   [OK] pyarrow installed (version: {getattr(pyarrow, '__version__', 'unknown')})")
    pyarrow_available = True
except (ImportError, NameError) as e:
    print(f"   [FAIL] pyarrow not installed: {e}")
    pyarrow_available = False

# 4. 检查 LanceDB 数据目录
print("\n[4] 检查 LanceDB 数据目录:")
try:
    from config.config import Config
    parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
    lance_dir = Path(parquet_dir) / 'lance_db'
    print(f"   目录路径: {lance_dir}")
    print(f"   目录存在: {lance_dir.exists()}")
    
    if lance_dir.exists():
        # 列出表
        tables = []
        for item in lance_dir.iterdir():
            if item.is_dir() and item.suffix == '':
                tables.append(item.name)
        print(f"   表列表: {tables}")
        
        # 检查 stock_daily 表
        stock_daily_dir = lance_dir / 'stock_daily.lance'
        if stock_daily_dir.exists():
            print(f"   [OK] stock_daily.lance exists")
        else:
            print(f"   [FAIL] stock_daily.lance not exists")
except Exception as e:
    print(f"   [FAIL] Check failed: {e}")

# 5. 尝试初始化 LanceDBManager
print("\n[5] 尝试初始化 LanceDBManager:")
if lancedb_available and pyarrow_available:
    try:
        from data_svc.lance_manager import LanceDBManager
        manager = LanceDBManager(table_name="stock_daily")
        print("   [OK] LanceDBManager initialized successfully")
        
        # 检查表是否存在
        if 'stock_daily' in manager.db.table_names():
            print("   [OK] stock_daily table exists")
            info = manager.get_table_info()
            print(f"   Table info: {info}")
        else:
            print("   [FAIL] stock_daily table not exists")
    except Exception as e:
        print(f"   [FAIL] LanceDBManager init failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("   Skipped (lancedb or pyarrow not installed)")

# 6. 检查 OptimizedStockDataQuery 的初始化逻辑
print("\n[6] 模拟 OptimizedStockDataQuery 初始化:")
try:
    backend = os.getenv("DB_BACKEND", "lancedb").lower()
    print(f"   环境变量 DB_BACKEND: {backend}")
    print(f"   应该使用 LanceDB: {backend == 'lancedb'}")
    
    if backend == "lancedb":
        if not lancedb_available:
            print("   → 会回退到 DuckDB（lancedb 未安装）")
        else:
            try:
                from data_svc.lance_manager import LanceDBManager
                manager = LanceDBManager(table_name="stock_daily")
                print("   → 应该使用 LanceDB（初始化成功）")
            except Exception as e:
                print(f"   → 会回退到 DuckDB（初始化失败: {e}）")
    elif backend == "duckdb":
        print("   → 会使用 DuckDB（环境变量设置）")
    else:
        print("   → 会使用 SQLite（环境变量设置或其他原因）")
except Exception as e:
    print(f"   [FAIL] Check failed: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)

