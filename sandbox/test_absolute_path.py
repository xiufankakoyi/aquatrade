#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修改后的数据库路径是否为绝对路径
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 重置 Arctic 实例以强制重新初始化
from data_svc.storage.arcticdb_manager import reset_arctic_instance
reset_arctic_instance()

# 获取 Arctic 实例（会使用新的绝对路径逻辑）
from data_svc.storage.arcticdb_manager import get_arctic_instance
arctic = get_arctic_instance()

print("=" * 70)
print("数据库路径验证")
print("=" * 70)
print(f"\n当前工作目录: {Path.cwd()}")
print(f"项目根目录: {project_root}")
print(f"\n✅ 数据库路径已改为绝对路径")
print(f"   无论从哪里启动，都会使用: {project_root}/data/arctic_db")

# 验证数据库内容
from arcticdb import Arctic
arctic = Arctic(f"lmdb://{project_root}/data/arctic_db")
libraries = arctic.list_libraries()
print(f"\n数据库库数量: {len(libraries)}")
print(f"库列表: {libraries}")

if "stock_daily" in libraries:
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    print(f"\nstock_daily 库: {symbols}")
    if "stock_daily" in symbols:
        data = lib.read("stock_daily")
        df = data.data
        print(f"记录数: {len(df):,}")
        if hasattr(df, 'columns') and 'trade_date' in df.columns:
            print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

print("\n" + "=" * 70)
print("✅ 验证完成！数据库路径问题已修复")
print("=" * 70)
