#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证因子数据是否正确写入
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

print("验证因子数据...")
print("=" * 70)

if "stock_daily" in arctic.list_libraries():
    lib = arctic["stock_daily"]
    if "stock_daily" in lib.list_symbols():
        data = lib.read("stock_daily")
        
        # 转换为 pandas
        if hasattr(data.data, 'to_pandas'):
            df = data.data.to_pandas()
        else:
            df = data.data
        
        print(f"数据形状: {df.shape}")
        print(f"\n所有列名 ({len(df.columns)} 个):")
        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. {col}")
        
        # 检查因子列
        factor_cols = [
            'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120',
            'rsi_6', 'rsi_12', 'rsi_24',
            'macd_dif', 'macd_dea', 'macd_bar',
            'kdj_k', 'kdj_d', 'kdj_j',
            'boll_upper', 'boll_mid', 'boll_lower', 'bb_width_20',
            'return_5d', 'return_20d', 'return_60d',
            'volatility_20d', 'max_drawdown_20d',
            'vol_ma5', 'vol_ma10', 'vol_ma20',
            'atr_14', 'cci_14', 'wr_14'
        ]
        
        existing_factors = [c for c in factor_cols if c in df.columns]
        
        print(f"\n\n存在的因子 ({len(existing_factors)} 个):")
        for col in existing_factors[:10]:
            non_null = df[col].notna().sum()
            print(f"  ✓ {col}: {non_null:,} 个非空值")
        if len(existing_factors) > 10:
            print(f"  ... 还有 {len(existing_factors) - 10} 个因子")
        
        # 显示样本数据
        if 'trade_date' in df.columns:
            print(f"\n\n样本数据 (最新一天):")
            latest_date = df['trade_date'].max()
            sample = df[df['trade_date'] == latest_date].head(3)
            display_cols = ['trade_date', 'stock_code', 'close'] + existing_factors[:5]
            print(sample[display_cols].to_string())
        
    else:
        print("stock_daily symbol 不存在")
else:
    print("stock_daily 库不存在")
