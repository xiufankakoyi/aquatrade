#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据清洗启动器
遍历 data_lake 下所有日期目录，清洗 JSON 数据
"""

import sys
import os
import time
import importlib.util

DATA_LAKE_DIR = r"c:\Users\Liu\Desktop\projects\quant\data_lake"
CLEANED_DATA_DIR = r"c:\Users\Liu\Desktop\projects\quant\data\cleaned_data"

def load_combined_module():
    """动态加载 combined.py 模块"""
    spec = importlib.util.spec_from_file_location("combined", os.path.join(os.path.dirname(__file__), "combined.py"))
    combined = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(combined)
    return combined

def clean_date(date_dir):
    """清洗单个日期的数据"""
    combined = load_combined_module()

    data_dir = os.path.join(DATA_LAKE_DIR, date_dir)
    output_dir = os.path.join(CLEANED_DATA_DIR, date_dir)

    if not os.path.exists(data_dir):
        print(f"[跳过] 目录不存在: {date_dir}")
        return False

    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    if not json_files:
        print(f"[跳过] 无 JSON 文件: {date_dir}")
        return False

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 50)
    print(f"   [清洗] 正在处理 {date_dir}")
    print("=" * 50)

    cleaner = combined.StockDataCleaner(data_dir, output_dir)
    cleaner.run()

    print(f"[完成] {date_dir} 清洗完成")
    return True

def main():
    print("=" * 50)
    print("   数据清洗启动器")
    print("   遍历 data_lake 下所有日期进行清洗")
    print("=" * 50)
    print()

    if not os.path.exists(DATA_LAKE_DIR):
        print(f"[错误] data_lake 目录不存在: {DATA_LAKE_DIR}")
        sys.exit(1)

    dates = sorted([d for d in os.listdir(DATA_LAKE_DIR)
                   if os.path.isdir(os.path.join(DATA_LAKE_DIR, d))],
                   reverse=True)

    if not dates:
        print("[警告] 没有找到任何日期目录")
        sys.exit(0)

    print(f"[INFO] 找到 {len(dates)} 个日期目录")
    print()

    cleaned_count = 0
    skipped_count = 0

    for i, date_dir in enumerate(dates):
        if i > 0:
            print("[INFO] 继续处理下一个日期...")
        success = clean_date(date_dir)
        if success:
            cleaned_count += 1
        else:
            skipped_count += 1

    print()
    print("=" * 50)
    print(f"   清洗完成!")
    print(f"   成功: {cleaned_count} 个")
    if skipped_count > 0:
        print(f"   跳过: {skipped_count} 个")
    print("=" * 50)

if __name__ == "__main__":
    main()
