#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 stock_daily 库的列名，看是否有因子数据
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    if "stock_daily" in lib.list_symbols():
        data = lib.read("stock_daily")
        df = data.data
        
        print("stock_daily 库的所有列名:")
        print("=" * 60)
        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. {col}")
        
        print("\n" + "=" * 60)
        print("检查常见的因子列:")
        factor_columns = [
            'ma5', 'ma10', 'ma20', 'ma30', 'ma60',
            'rsi_6', 'rsi_12', 'rsi_24',
            'macd', 'macd_signal', 'macd_hist',
            'kdj_k', 'kdj_d', 'kdj_j',
            'boll_upper', 'boll_middle', 'boll_lower',
            'vol_ma5', 'vol_ma10', 'vol_ma20',
            'atr', 'cci', 'wr', 'obv',
            'return_5d', 'return_20d', 'return_60d',
            'volatility_20d', 'max_drawdown_20d',
            'beta_60d', 'alpha_60d'
        ]
        
        for col in factor_columns:
            if col in df.columns:
                non_null = df[col].notna().sum()
                print(f"  ✓ {col}: {non_null} 个非空值")
            else:
                print(f"  ✗ {col}: 不存在")
    else:
        print("stock_daily symbol 不存在")
else:
    print("stock_daily 库不存在")
