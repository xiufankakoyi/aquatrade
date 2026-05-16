"""
测试因子矩阵构建
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import get_unified_manager
from core.backtest.factor_matrix import FactorMatrixBuilder

print("=" * 70)
print("测试因子矩阵构建")
print("=" * 70)

# 读取数据
manager = get_unified_manager()
start_date = '2024-12-31'
end_date = '2025-01-31'

print(f"\n[1] 读取数据: {start_date} ~ {end_date}")
df = manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"   数据形状: {df.shape}")

if df.is_empty():
    print("   ⚠️ 数据为空!")
else:
    print(f"   列名: {df.columns}")
    
    # 检查关键列
    key_cols = ['trade_date', 'stock_code', 'open', 'close', 'ma5', 'ma10']
    for col in key_cols:
        if col in df.columns:
            print(f"   ✓ {col}")
        else:
            print(f"   ✗ {col} 缺失!")
    
    # 构建因子矩阵
    print(f"\n[2] 构建因子矩阵...")
    
    # 计算状态字段
    import polars as pl
    df_enhanced = df.with_columns([
        (pl.col('close') >= pl.col('limit_up')).cast(pl.Float64).alias('is_limit_up'),
        (pl.col('close') <= pl.col('limit_down')).cast(pl.Float64).alias('is_limit_down'),
        ((pl.col('volume') == 0) | (pl.col('close') == 0)).cast(pl.Float64).alias('is_suspended')
    ])
    
    builder = FactorMatrixBuilder()
    fm = builder.build_from_single_dataframe(df_enhanced, use_cache=False)
    
    print(f"   因子矩阵形状: {fm.values.shape}")
    print(f"   日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    print(f"   日期数量: {len(fm.dates)}")
    print(f"   股票数量: {len(fm.codes_str)}")
    print(f"   因子数量: {len(fm.factor_names)}")
    
    # 检查 000001 的数据
    if '000001' in fm.codes_str:
        stock_idx = fm.codes_str.index('000001')
        print(f"\n[3] 检查 000001 的数据")
        print(f"   股票索引: {stock_idx}")
        
        # 检查 2025-01-23
        date_str = '2025-01-23'
        date_idx = fm.date_to_idx.get(date_str, -1)
        print(f"   {date_str} 索引: {date_idx}")
        
        if date_idx >= 0:
            factor_slice = fm.values[date_idx, stock_idx, :]
            print(f"\n   {date_str} 000001 的因子数据:")
            for i, name in enumerate(fm.factor_names):
                print(f"     {name}: {factor_slice[i]}")

print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)
