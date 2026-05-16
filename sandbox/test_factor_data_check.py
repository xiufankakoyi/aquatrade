"""
检查因子矩阵中的实际数据
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine

print("=" * 70)
print("检查因子矩阵中的实际数据")
print("=" * 70)

# 初始化
data_query = OptimizedStockDataQuery()
engine = UnifiedBacktestEngine(data_query)

# 预加载数据
print("\n[1] 预加载数据...")
engine._preload_data(pd.Timestamp('2025-01-01'), pd.Timestamp('2025-01-31'))

# 检查因子矩阵
print("\n[2] 检查因子矩阵...")
fm = engine._factor_matrix
if fm:
    print(f"   因子矩阵形状: {fm.values.shape}")
    print(f"   日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    
    # 找到 000001 的索引
    if '000001' in fm.codes_str:
        stock_idx = fm.codes_str.index('000001')
        print(f"\n[3] 000001 的数据 (索引: {stock_idx})")
        
        # 找到 ma5 和 ma10 的因子索引
        ma5_idx = fm.factor_names.index('ma5')
        ma10_idx = fm.factor_names.index('ma10')
        
        print(f"   ma5 因子索引: {ma5_idx}")
        print(f"   ma10 因子索引: {ma10_idx}")
        
        # 打印前20天的数据
        print(f"\n[4] 前20天的 MA 数据:")
        print(f"{'日期':<12} {'MA5':>10} {'MA10':>10} {'是否NaN':>10}")
        print("-" * 50)
        
        for t in range(min(20, len(fm.dates))):
            date = fm.dates[t]
            ma5_val = fm.values[t, stock_idx, ma5_idx]
            ma10_val = fm.values[t, stock_idx, ma10_idx]
            is_nan = np.isnan(ma5_val) or np.isnan(ma10_val)
            print(f"{date:<12} {ma5_val:>10.2f} {ma10_val:>10.2f} {'Yes' if is_nan else 'No':>10}")
        
        # 找到第一个非NaN的日期
        print(f"\n[5] 查找第一个非NaN的日期...")
        for t in range(len(fm.dates)):
            ma5_val = fm.values[t, stock_idx, ma5_idx]
            ma10_val = fm.values[t, stock_idx, ma10_idx]
            if not np.isnan(ma5_val) and not np.isnan(ma10_val):
                print(f"   第一个非NaN日期: {fm.dates[t]}")
                print(f"   MA5: {ma5_val:.2f}, MA10: {ma10_val:.2f}")
                break
        
        # 检查 2025-01-23 的数据
        date_str = '2025-01-23'
        if date_str in fm.date_to_idx:
            t_idx = fm.date_to_idx[date_str]
            ma5_val = fm.values[t_idx, stock_idx, ma5_idx]
            ma10_val = fm.values[t_idx, stock_idx, ma10_idx]
            print(f"\n[6] {date_str} 的数据:")
            print(f"   MA5: {ma5_val:.2f}")
            print(f"   MA10: {ma10_val:.2f}")
            
            # 检查前一天
            if t_idx > 0:
                prev_date = fm.dates[t_idx - 1]
                prev_ma5 = fm.values[t_idx - 1, stock_idx, ma5_idx]
                prev_ma10 = fm.values[t_idx - 1, stock_idx, ma10_idx]
                print(f"   前一天 ({prev_date}): MA5={prev_ma5:.2f}, MA10={prev_ma10:.2f}")
                
                # 检查是否是死叉
                if prev_ma5 > prev_ma10 and ma5_val < ma10_val:
                    print(f"   ✓ 这是死叉信号！")

print("\n" + "=" * 70)
print("检查完成!")
print("=" * 70)
