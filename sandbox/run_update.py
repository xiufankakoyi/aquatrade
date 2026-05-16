#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行数据更新
"""
import sys
import os
import shutil
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def cleanup_corrupted_libraries():
    """清理损坏的库（保留 stock_daily 和有效的库）"""
    arctic_path = project_root / 'data' / 'arctic_db'
    
    # 只删除损坏的库目录（大小小于 1MB 的是损坏的）
    for lib_name in ['benchmark', 'benchmark_daily', 'factor', 'limit_status', 'stock_basic', 'stock_info']:
        lib_dir = arctic_path / lib_name
        if lib_dir.exists():
            data_file = lib_dir / 'data.mdb'
            if data_file.exists():
                size = data_file.stat().st_size
                if size < 1000000:  # 小于 1MB 的是损坏的
                    try:
                        shutil.rmtree(lib_dir)
                        print(f"已清理损坏的库: {lib_name} (大小: {size} 字节)")
                    except Exception as e:
                        print(f"清理库 {lib_name} 失败: {e}")
            else:
                try:
                    shutil.rmtree(lib_dir)
                    print(f"已清理空库: {lib_name}")
                except Exception as e:
                    print(f"清理库 {lib_name} 失败: {e}")

cleanup_corrupted_libraries()

from data_svc.storage.unified_updater import UnifiedDataUpdater
from datetime import datetime

print("=" * 70)
print("运行数据更新")
print("=" * 70)

updater = UnifiedDataUpdater()
result = updater.run_full_update(
    start_date='20260214',
    end_date='20260228',
    skip_factors=False
)

print(f"\n更新结果:")
print(f"  成功: {result.success}")
print(f"  消息: {result.message}")
print(f"  股票日期更新: {result.stock_dates_updated}")
print(f"  股票记录添加: {result.stock_records_added}")
print(f"  基准日期更新: {result.benchmark_dates_updated}")
print(f"  基准记录添加: {result.benchmark_records_added}")
print(f"  因子记录计算: {result.factor_records_computed}")
print(f"  错误: {result.errors}")

print("\n" + "=" * 70)
