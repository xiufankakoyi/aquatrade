#!/usr/bin/env python3
"""
快速移除调试日志脚本

此脚本会扫描项目文件，移除所有直接写入 debug.log 的代码，
替换为使用标准 logging 模块。

使用方法:
    python scripts/remove_debug_logs.py [--dry-run] [--file <file_path>]
"""

import re
import os
import sys
from pathlib import Path
from typing import List, Tuple

# 需要处理的文件列表
TARGET_FILES = [
    'server/visualization_api.py',
    'core/backtest/optimized_backtest_engine.py',
    'data_svc/database/optimized_data_query.py',
]

# 调试日志模式
DEBUG_LOG_PATTERN = re.compile(
    r'#\s*#region\s+agent\s+log.*?#\s*#endregion',
    re.DOTALL | re.MULTILINE
)

# 单个调试日志写入模式
SINGLE_LOG_PATTERN = re.compile(
    r'try:\s*'
    r'with\s+open\([^)]*debug\.log[^)]*\)\s+as\s+f:\s*'
    r'f\.write\([^)]+\)\s*\+?\s*["\']\\n["\']?\s*'
    r'f\.flush\(\)\s*'
    r'except[^:]*:\s*pass',
    re.DOTALL | re.MULTILINE
)


def find_debug_logs(content: str) -> List[Tuple[int, str]]:
    """查找所有调试日志代码块"""
    matches = []
    
    # 查找调试日志区域块
    for match in DEBUG_LOG_PATTERN.finditer(content):
        start = content[:match.start()].count('\n') + 1
        matches.append((start, match.group(0)))
    
    # 查找单个日志写入
    for match in SINGLE_LOG_PATTERN.finditer(content):
        start = content[:match.start()].count('\n') + 1
        matches.append((start, match.group(0)))
    
    return matches


def remove_debug_logs(content: str) -> str:
    """移除调试日志代码"""
    # 移除调试日志区域块
    content = DEBUG_LOG_PATTERN.sub('', content)
    
    # 移除单个日志写入
    content = SINGLE_LOG_PATTERN.sub('', content)
    
    # 清理多余的空行（连续3个以上空行变为2个）
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    return content


def process_file(file_path: Path, dry_run: bool = False) -> Tuple[int, int]:
    """处理单个文件"""
    if not file_path.exists():
        print(f"[WARN] 文件不存在: {file_path}")
        return 0, 0

    print(f"[FILE] 处理文件: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[FAIL] 读取文件失败: {e}")
        return 0, 0

    # 查找调试日志
    matches = find_debug_logs(content)

    if not matches:
        print(f"   [OK] 未找到调试日志")
        return 0, 0

    print(f"   [FOUND] 找到 {len(matches)} 处调试日志")

    if dry_run:
        # 只显示，不修改
        for line_num, code in matches[:5]:  # 只显示前5个
            print(f"   行 {line_num}: {code[:50]}...")
        if len(matches) > 5:
            print(f"   ... 还有 {len(matches) - 5} 处")
        return len(matches), 0

    # 移除调试日志
    new_content = remove_debug_logs(content)
    
    if new_content == content:
        print(f"   [WARN] 内容未变化")
        return len(matches), 0
    
    # 写入文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"   [OK] 已移除 {len(matches)} 处调试日志")
        return len(matches), len(matches)
    except Exception as e:
        print(f"   [FAIL] 写入文件失败: {e}")
        return len(matches), 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='移除调试日志')
    parser.add_argument('--dry-run', action='store_true', help='只显示，不修改')
    parser.add_argument('--file', type=str, help='只处理指定文件')
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    
    if args.file:
        # 只处理指定文件
        file_path = project_root / args.file
        if not file_path.exists():
            print(f"[FAIL] 文件不存在: {file_path}")
            sys.exit(1)
        files = [file_path]
    else:
        # 处理所有目标文件
        files = [project_root / f for f in TARGET_FILES]
    
    print(f"{'[SCAN] 扫描模式' if args.dry_run else '[FIX] 修复模式'}")
    print(f"处理 {len(files)} 个文件\n")
    
    total_found = 0
    total_removed = 0
    
    for file_path in files:
        found, removed = process_file(file_path, dry_run=args.dry_run)
        total_found += found
        total_removed += removed
        print()
    
    print(f"[STATS] 统计:")
    print(f"   找到: {total_found} 处")
    if not args.dry_run:
        print(f"   移除: {total_removed} 处")
    
    if args.dry_run:
        print("\n提示: 直接运行（不加 --dry-run）来实际移除日志")


if __name__ == '__main__':
    main()

