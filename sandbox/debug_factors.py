#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试因子计算
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.factor_precompute_service import FactorPrecomputeService

service = FactorPrecomputeService()

# 加载基础数据
df = service._load_base_data('2026-02-01', '2026-02-28')

if df is not None:
    print(f"加载数据: {len(df):,} 行")
    print(f"列名: {df.columns.tolist()}")
    print(f"\n前5行:")
    print(df[['trade_date', 'stock_code', 'close']].head())
    
    # 计算因子
    print("\n\n开始计算因子...")
    df_with_factors = service._compute_factors_vectorized(df)
    
    print(f"\n计算后列数: {len(df_with_factors.columns)}")
    print(f"新增因子列:")
    
    factor_cols = ['ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120',
                   'rsi_6', 'rsi_12', 'rsi_24',
                   'macd_dif', 'macd_dea', 'macd_bar',
                   'kdj_k', 'kdj_d', 'kdj_j']
    
    for col in factor_cols:
        if col in df_with_factors.columns:
            non_null = df_with_factors[col].notna().sum()
            print(f"  {col}: {non_null:,} 个非空值")
    
    print(f"\n样本数据 (000001):")
    sample = df_with_factors[df_with_factors['stock_code'] == '000001'].head(10)
    print(sample[['trade_date', 'close', 'ma5', 'rsi_6', 'macd_dif', 'kdj_k']].to_string())
else:
    print("加载数据失败")
