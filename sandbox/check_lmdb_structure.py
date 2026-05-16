"""
检查 ArcticDB LMDB 结构（不使用 lmdb 模块）
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import os
from loguru import logger


def check_lmdb_structure():
    """检查 LMDB 结构"""
    base_path = Path('data/arctic_db')
    
    print("=" * 70)
    print("检查 LMDB 目录结构")
    print("=" * 70)
    
    for lib_dir in sorted(base_path.iterdir()):
        if not lib_dir.is_dir():
            continue
        
        lib_name = lib_dir.name
        print(f"\n{lib_name}:")
        
        # 查找所有 mdb 文件
        mdb_files = list(lib_dir.rglob('*.mdb'))
        
        total_size = 0
        for mdb_file in mdb_files:
            size_mb = mdb_file.stat().st_size / (1024 * 1024)
            total_size += mdb_file.stat().st_size
            rel_path = mdb_file.relative_to(lib_dir)
            print(f"  {rel_path}: {size_mb:.2f} MB")
        
        print(f"  总大小: {total_size / (1024*1024):.2f} MB")


def check_library_count():
    """检查库数量"""
    base_path = Path('data/arctic_db')
    
    print("\n" + "=" * 70)
    print("库统计")
    print("=" * 70)
    
    libs = [d for d in base_path.iterdir() if d.is_dir()]
    print(f"总库数: {len(libs)}")
    
    # 检查哪些库有实际数据
    has_data = []
    empty = []
    
    for lib_dir in libs:
        mdb_files = list(lib_dir.rglob('*.mdb'))
        data_files = [f for f in mdb_files if '_arctic_cfg' not in str(f) and f.stat().st_size > 10000]
        
        if data_files:
            has_data.append(lib_dir.name)
        else:
            empty.append(lib_dir.name)
    
    print(f"\n有数据的库 ({len(has_data)}):")
    for name in has_data:
        print(f"  ✅ {name}")
    
    print(f"\n空库 ({len(empty)}):")
    for name in empty:
        print(f"  📭 {name}")


if __name__ == '__main__':
    check_lmdb_structure()
    check_library_count()
