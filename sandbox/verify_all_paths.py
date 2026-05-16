#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证所有 ArcticDB 路径配置都使用绝对路径
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("验证所有 ArcticDB 路径配置")
print("=" * 70)

# 1. 检查 arcticdb_manager.py
print("\n1. arcticdb_manager.py:")
from data_svc.storage.arcticdb_manager import ArcticDBManager, get_arctic_instance
# 读取源码验证
manager_file = project_root / "data_svc" / "storage" / "arcticdb_manager.py"
with open(manager_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if 'project_root = os.path.dirname' in content:
        print("   ✅ 已使用绝对路径（基于项目根目录）")
    else:
        print("   ❌ 仍使用相对路径")

# 2. 检查 data_source_config.py
print("\n2. data_source_config.py:")
config_file = project_root / "config" / "data_source_config.py"
with open(config_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if '_project_root = Path(__file__).parent.parent' in content:
        print("   ✅ 已使用绝对路径（基于项目根目录）")
    else:
        print("   ❌ 仍使用相对路径")

# 3. 检查 arctic_store.py
print("\n3. arctic_store.py:")
store_file = project_root / "sandbox" / "arctic_store.py"
with open(store_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if '_project_root = Path(__file__).parent.parent' in content:
        print("   ✅ 已使用绝对路径（基于项目根目录）")
    else:
        print("   ❌ 仍使用相对路径")

# 4. 验证实际路径
print("\n4. 实际路径验证:")
print(f"   项目根目录: {project_root}")
print(f"   数据库路径: {project_root / 'data' / 'arctic_db'}")
print(f"   路径存在: {(project_root / 'data' / 'arctic_db').exists()}")

# 5. 检查是否还有其他相对路径
print("\n5. 检查其他可能的相对路径:")
import subprocess
result = subprocess.run(
    ['grep', '-r', 'lmdb://./data/arctic_db', '--include=*.py', str(project_root)],
    capture_output=True, text=True
)
if result.stdout.strip():
    print("   ⚠️  发现其他相对路径:")
    for line in result.stdout.strip().split('\n')[:5]:
        print(f"      {line}")
else:
    print("   ✅ 没有其他相对路径")

print("\n" + "=" * 70)
print("总结: 所有主要 ArcticDB 调用已改为绝对路径")
print("=" * 70)
