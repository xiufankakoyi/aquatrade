#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quant 爬虫启动器
支持格式: 单日期 2025.12.16 或 范围 2025.12.16-2026.1.12
"""

import sys
import io

# 设置 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import subprocess
import time
from datetime import datetime, timedelta

def parse_date(date_str):
    """解析 YYYY.MM.DD, YYYY-M-D, YYYY-MM-DD 或 YYYY-M-DD 格式"""
    date_str = date_str.strip()
    # 尝试多种格式
    formats = ["%Y.%m.%d", "%Y-%m-%d", "%Y.%m.%d", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期格式: {date_str}")

def format_date(dt):
    """格式化为 YYYY-MM-DD"""
    return dt.strftime("%Y-%m-%d")

def run_crawler(date_str):
    """运行爬虫"""
    cmd = [sys.executable, "main.py", "--date", date_str]
    print("=" * 50)
    print(f"   [爬虫] 正在爬取 {date_str} 的数据")
    print("=" * 50)
    result = subprocess.run(cmd)
    return result.returncode == 0

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  main.bat 2025.12.16                    # 单个日期")
        print("  main.bat 2025.12.16-2026.1.12          # 日期范围")
        sys.exit(1)

    input_arg = sys.argv[1]

    # 检测是否是日期范围模式 (格式: YYYY-MM-DD-YYYY-MM-DD 或 YYYY.MM.DD-YYYY.MM.DD)
    # 日期范围需要至少4个数字段（YYYY-MM-DD-YYYY-MM-DD）
    # 单日期只有2个数字段（YYYY-MM-DD）
    dash_count = input_arg.count('-')
    dot_count = input_arg.count('.')
    
    # 统计数字段数量来区分单日期和日期范围
    # 单日期: 2026-01-28 -> 3段 (YYYY, MM, DD)
    # 日期范围: 2026-01-16-2026-01-28 -> 6段
    def count_segments(separator):
        return len(input_arg.split(separator))
    
    dash_segments = count_segments('-')
    dot_segments = count_segments('.')
    
    # 如果有6个段，则是日期范围；否则是单日期
    is_range = (dash_segments == 6) or (dot_segments == 6)
    
    if is_range:
        # 日期范围模式
        # 格式: YYYY-MM-DD-YYYY-MM-DD 或 YYYY.MM.DD-YYYY.MM.DD
        # 需要找到中间的分隔符
        if dash_segments == 6:
            # 2026-01-26-2026-01-28
            # 中间分隔符在第 3 个 '-' 的位置
            # 先找到第 3 个 '-' 的索引
            parts = input_arg.split('-')
            # parts = ['2026', '01', '26', '2026', '01', '28']
            # 开始日期 = parts[0-2]，结束日期 = parts[3-5]
            start_str = '-'.join(parts[0:3])
            end_str = '-'.join(parts[3:6])
        else:
            parts = input_arg.split('.')
            start_str = '.'.join(parts[0:3])
            end_str = '.'.join(parts[3:6])

        print(f"[INFO] 检测到日期范围模式")
        print(f"[INFO] 开始日期: {start_str}")
        print(f"[INFO] 结束日期: {end_str}")
        print()

        try:
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
        except ValueError as e:
            print(f"[错误] 日期格式解析失败: {e}")
            sys.exit(1)

        current = start_date
        while current <= end_date:
            date_formatted = format_date(current)
            success = run_crawler(date_formatted)

            if success:
                print(f"[完成] {date_formatted} 数据爬取完成")
            else:
                print(f"[警告] {date_formatted} 爬取出错")

            if current < end_date:
                print("[延迟] 等待 10 秒后继续下一个日期...")
                time.sleep(10)

            current += timedelta(days=1)

    else:
        # 单日期模式
        print(f"[INFO] 检测到单个日期模式")
        print()

        try:
            date = parse_date(input_arg)
            date_formatted = format_date(date)
            run_crawler(date_formatted)
        except ValueError as e:
            print(f"[错误] 日期格式解析失败: {e}")
            sys.exit(1)

    print()
    print("=" * 50)
    print("   任务完成!")
    print("=" * 50)

if __name__ == "__main__":
    main()
