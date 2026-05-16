#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为所有历史数据预计算因子
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.factor_precompute_service import FactorPrecomputeService


def main():
    print("=" * 70)
    print("预计算所有历史数据的因子")
    print("=" * 70)
    
    service = FactorPrecomputeService()
    
    # 预计算 2010-01-01 到 2026-02-28 的所有因子
    result = service.precompute_all_factors(
        start_date='2010-01-01',
        end_date='2026-02-28',
        batch_days=90  # 每批处理90天，避免内存溢出
    )
    
    print("\n" + "=" * 70)
    # 处理 FactorComputeResult 对象
    if hasattr(result, 'success'):
        if result.success:
            print("✓ 因子预计算完成!")
            print(f"  处理记录数: {result.records_computed:,}")
            print(f"  消息: {result.message}")
        else:
            print(f"✗ 预计算失败: {result.error}")
    else:
        # 处理字典结果
        if result.get('success'):
            print("✓ 因子预计算完成!")
            print(f"  处理记录数: {result.get('records_computed', 0):,}")
            print(f"  消息: {result.get('message', '')}")
        else:
            print(f"✗ 预计算失败: {result.get('error', 'Unknown error')}")
    print("=" * 70)


if __name__ == '__main__':
    main()
