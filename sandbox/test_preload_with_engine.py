"""
使用引擎预加载测试
"""
import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine

print("=" * 70)
print("使用引擎预加载测试")
print("=" * 70)

# 初始化
data_query = OptimizedStockDataQuery()
engine = UnifiedBacktestEngine(data_query)

print("\n[1] 调用 _preload_data...")
result = engine._preload_data(pd.Timestamp('2025-01-01'), pd.Timestamp('2025-01-31'))

print(f"\n[2] 预加载结果:")
print(f"   结果类型: {type(result)}")
if result:
    print(f"   结果键: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
    if 'stock_daily' in result:
        df = result['stock_daily']
        print(f"   stock_daily 形状: {df.shape if hasattr(df, 'shape') else 'N/A'}")
else:
    print(f"   结果为空!")

print(f"\n[3] 检查因子矩阵:")
if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"   因子矩阵形状: {fm.values.shape}")
    print(f"   日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
else:
    print(f"   因子矩阵为空!")

print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)
