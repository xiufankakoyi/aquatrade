#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理冗余文件和代码

使用方法:
    python scripts/cleanup_redundant_files.py [--dry-run]

参数:
    --dry-run: 只显示将要删除/移动的文件，不实际执行
"""
import os
import sys
import argparse
from pathlib import Path

# 要删除的文件列表（测试/调试脚本）
FILES_TO_DELETE = [
    # 测试文件
    "test.py",
    "test1.py", 
    "test2.py",
    "test_backtest_performance.py",
    
    # 调试脚本
    "auto_debug_backtest.py",
    "debug_backtest_playwright.py",
    "debug_perf.py",
    "debug_start.bat",
    "debug_streaming_backtest.py",
]

# 要移动的文件（从根目录移动到 scripts/）
FILES_TO_MOVE = {
    "check_db_backend.py": "scripts/check_db_backend.py",
}

# 要检查的文件（需要手动确认）
FILES_TO_CHECK = [
    "data_svc/spider/app.py",  # 可能是旧的 Flask 应用
    "core/strategies/1.py",    # 测试文件
    "analyze_logs.py",         # 日志分析脚本（可选）
]

def main():
    parser = argparse.ArgumentParser(description='清理冗余文件')
    parser.add_argument('--dry-run', action='store_true', 
                       help='只显示将要删除/移动的文件，不实际执行')
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    
    print("=" * 60)
    print("项目清理工具")
    if args.dry_run:
        print("【DRY RUN 模式 - 不会实际删除/移动文件】")
    print("=" * 60)
    
    # 1. 删除文件
    print("\n[1] 删除冗余文件...")
    deleted_count = 0
    for file in FILES_TO_DELETE:
        file_path = project_root / file
        if file_path.exists():
            if args.dry_run:
                print(f"  [DRY RUN] 将删除: {file}")
            else:
                try:
                    file_path.unlink()
                    print(f"  [OK] 已删除: {file}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  [FAIL] 删除失败: {file} - {e}")
        else:
            print(f"  - 不存在: {file}")
    
    if not args.dry_run:
        print(f"\n  总计删除: {deleted_count} 个文件")
    
    # 2. 移动文件
    print("\n[2] 移动文件到 scripts/ 目录...")
    moved_count = 0
    for src, dst in FILES_TO_MOVE.items():
        src_path = project_root / src
        dst_path = project_root / dst
        
        if src_path.exists():
            if args.dry_run:
                print(f"  [DRY RUN] 将移动: {src} -> {dst}")
            else:
                try:
                    # 确保目标目录存在
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 如果目标文件已存在，询问是否覆盖
                    if dst_path.exists():
                        response = input(f"  目标文件已存在: {dst}，是否覆盖？(y/n): ")
                        if response.lower() != 'y':
                            print(f"  - 跳过: {src}")
                            continue
                    
                    src_path.rename(dst_path)
                    print(f"  [OK] 已移动: {src} -> {dst}")
                    moved_count += 1
                except Exception as e:
                    print(f"  [FAIL] 移动失败: {src} - {e}")
        else:
            print(f"  - 不存在: {src}")
    
    if not args.dry_run:
        print(f"\n  总计移动: {moved_count} 个文件")
    
    # 3. 检查文件
    print("\n[3] 需要手动检查的文件:")
    for file in FILES_TO_CHECK:
        file_path = project_root / file
        if file_path.exists():
            print(f"  [WARN] {file} - 需要确认是否还在使用")
            # 显示文件大小和修改时间
            stat = file_path.stat()
            size_kb = stat.st_size / 1024
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"      大小: {size_kb:.1f} KB, 修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"  - {file} - 不存在")
    
    # 4. 检查 __pycache__ 目录
    print("\n[4] 检查 __pycache__ 目录...")
    pycache_dirs = list(project_root.rglob("__pycache__"))
    if pycache_dirs:
        print(f"  发现 {len(pycache_dirs)} 个 __pycache__ 目录")
        if not args.dry_run:
            response = input("  是否删除所有 __pycache__ 目录？(y/n): ")
            if response.lower() == 'y':
                deleted_pycache = 0
                for pycache_dir in pycache_dirs:
                    try:
                        import shutil
                        shutil.rmtree(pycache_dir)
                        deleted_pycache += 1
                    except Exception as e:
                        print(f"  [FAIL] 删除失败: {pycache_dir} - {e}")
                print(f"  [OK] 已删除 {deleted_pycache} 个 __pycache__ 目录")
    else:
        print("  [OK] 没有发现 __pycache__ 目录")
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN 完成！使用不带 --dry-run 参数运行以实际执行清理。")
    else:
        print("清理完成！")
    print("=" * 60)
    
    # 提示
    if not args.dry_run:
        print("\n提示:")
        print("  1. 建议运行测试确保项目仍然正常")
        print("  2. 检查 git 状态: git status")
        print("  3. 如果一切正常，提交更改: git commit -am 'Clean up redundant files'")

if __name__ == "__main__":
    main()

