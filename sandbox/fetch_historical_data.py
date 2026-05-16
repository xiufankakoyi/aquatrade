#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拉取历史股票数据

用于补充数据库中的历史数据，支持全量更新或指定日期范围。
"""
import os
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime
from data_svc.storage.unified_updater import UnifiedDataUpdater


def main():
    parser = argparse.ArgumentParser(description='拉取历史股票数据')
    parser.add_argument('--start-date', type=str, default='20200101',
                        help='开始日期 (YYYYMMDD)，默认 20200101')
    parser.add_argument('--end-date', type=str, default=None,
                        help='结束日期 (YYYYMMDD)，默认今天')
    parser.add_argument('--skip-benchmark', action='store_true',
                        help='跳过指数数据更新')
    
    args = parser.parse_args()
    
    if args.end_date is None:
        args.end_date = datetime.now().strftime('%Y%m%d')
    
    print("=" * 70)
    print("历史数据拉取")
    print("=" * 70)
    print(f"日期范围: {args.start_date} ~ {args.end_date}")
    print()
    
    updater = UnifiedDataUpdater()
    
    result = updater.run_full_update(
        start_date=args.start_date,
        end_date=args.end_date,
        skip_benchmark=args.skip_benchmark
    )
    
    print("\n" + "=" * 70)
    if result.success:
        print(f"✓ 更新成功!")
        print(f"  股票日期更新: {result.stock_dates_updated}")
        print(f"  股票记录新增: {result.stock_records_added:,}")
        print(f"  指数日期更新: {result.benchmark_dates_updated}")
        print(f"  指数记录新增: {result.benchmark_records_added:,}")
    else:
        print(f"✗ 更新失败: {result.message}")
        if result.errors:
            for error in result.errors[:5]:
                print(f"  - {error}")
    print("=" * 70)


if __name__ == '__main__':
    main()
