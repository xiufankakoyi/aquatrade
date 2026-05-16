"""
检查因子矩阵的日期范围
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.backtest.factor_matrix import FactorMatrix

print("=" * 70)
print("检查因子矩阵日期范围")
print("=" * 70)

try:
    fm = FactorMatrix()
    fm.load_from_arctic('stock_daily', '2025-01-01', '2025-01-31')
    
    if fm.values is not None:
        print(f"\n因子矩阵形状: {fm.values.shape}")
        print(f"日期数量: {len(fm.dates)}")
        print(f"\n日期范围:")
        print(f"  开始: {fm.dates[0]}")
        print(f"  结束: {fm.dates[-1]}")
        print(f"\n所有日期:")
        for i, date in enumerate(fm.dates):
            print(f"  {i+1}. {date}")
    else:
        print("⚠️ 因子矩阵为空")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
