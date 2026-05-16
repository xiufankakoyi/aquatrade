#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量爬取 DragonEye 数据"""

import subprocess
import sys
import time
from datetime import datetime, timedelta


def crawl_date(date_str: str):
    """爬取指定日期的数据"""
    print(f"\n{'='*60}")
    print(f"爬取日期: {date_str}")
    print(f"{'='*60}")
    
    cmd = [sys.executable, "main_launcher.py", date_str]
    result = subprocess.run(cmd, cwd="c:\\Users\\Liu\\Desktop\\projects\\aquatrade\\quant")
    return result.returncode == 0


def batch_crawl(start_date: str, end_date: str):
    """批量爬取日期范围的数据"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    success_count = 0
    fail_count = 0
    
    print(f"\n{'='*60}")
    print(f"开始批量爬取: {start_date} 到 {end_date}")
    print(f"{'='*60}\n")
    
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        
        if crawl_date(date_str):
            success_count += 1
        else:
            fail_count += 1
        
        # 休息 5 秒避免请求过快
        time.sleep(5)
        
        current += timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"爬取完成: 成功 {success_count} 天, 失败 {fail_count} 天")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        batch_crawl(sys.argv[1], sys.argv[2])
    else:
        # 默认爬取 2025-04-12 到 2025-04-20
        batch_crawl('2025-04-12', '2025-04-20')
