#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试股票筛选器数据加载"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from server.routes.screener_data_service import get_screener_service

def test_screener_data():
    """测试股票筛选器数据加载"""
    service = get_screener_service()
    
    # 测试日期
    test_date = "2025-04-18"
    
    # 测试字段
    test_fields = ['stock_code', 'stock_name', 'close', 'total_mv', 'corr_60d', 'beta_60d', 'alpha_60d']
    
    print(f"\n{'='*60}")
    print(f"测试日期: {test_date}")
    print(f"测试字段: {test_fields}")
    print(f"{'='*60}\n")
    
    # 获取数据
    df = service.get_data(date=test_date, fields=test_fields)
    
    if df is None or df.is_empty():
        print("ERROR: 无法获取数据")
        return
    
    print(f"\n数据加载成功: {len(df)} 行, {len(df.columns)} 列")
    print(f"列: {df.columns}")
    
    # 检查关键字段
    print(f"\n--- 字段检查 ---")
    
    # stock_name
    if 'stock_name' in df.columns:
        null_count = df['stock_name'].null_count()
        non_null = len(df) - null_count
        print(f"stock_name: 非空={non_null}, 空={null_count}")
        if non_null > 0:
            sample = df.filter(df['stock_name'].is_not_null()).select(['stock_code', 'stock_name']).head(3)
            print(f"样例:\n{sample}")
    else:
        print("stock_name: 列不存在")
    
    # corr_60d
    if 'corr_60d' in df.columns:
        null_count = df['corr_60d'].null_count()
        non_null = len(df) - null_count
        print(f"\ncorr_60d: 非空={non_null}, 空={null_count}")
        if non_null > 0:
            sample = df.filter(df['corr_60d'].is_not_null()).select(['stock_code', 'corr_60d']).head(3)
            print(f"样例:\n{sample}")
    else:
        print("\ncorr_60d: 列不存在")
    
    # beta_60d
    if 'beta_60d' in df.columns:
        null_count = df['beta_60d'].null_count()
        non_null = len(df) - null_count
        print(f"\nbeta_60d: 非空={non_null}, 空={null_count}")
        if non_null > 0:
            sample = df.filter(df['beta_60d'].is_not_null()).select(['stock_code', 'beta_60d']).head(3)
            print(f"样例:\n{sample}")
    else:
        print("\nbeta_60d: 列不存在")
    
    # alpha_60d
    if 'alpha_60d' in df.columns:
        null_count = df['alpha_60d'].null_count()
        non_null = len(df) - null_count
        print(f"\nalpha_60d: 非空={non_null}, 空={null_count}")
        if non_null > 0:
            sample = df.filter(df['alpha_60d'].is_not_null()).select(['stock_code', 'alpha_60d']).head(3)
            print(f"样例:\n{sample}")
    else:
        print("\nalpha_60d: 列不存在")
    
    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}")

if __name__ == '__main__':
    test_screener_data()
