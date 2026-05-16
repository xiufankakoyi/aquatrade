"""
检查Tushare的MA值计算
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd

print("=" * 70)
print("检查Tushare的MA值计算")
print("=" * 70)

try:
    # 从ArcticDB读取000001的收盘价数据
    print("\n[1] 读取000001的收盘价数据...")
    
    from data_svc.unified_data_manager import get_unified_manager
    manager = get_unified_manager()
    
    # 读取2024-12-01到2025-01-20的数据
    df = manager.read('stock_daily', start_date='2024-12-01', end_date='2025-01-20', use_cache=False)
    
    if df.is_empty():
        print("  ⚠️ 数据为空")
        sys.exit(1)
    
    # 过滤000001的数据
    df_000001 = df.filter(df['stock_code'] == '000001')
    
    if df_000001.is_empty():
        print("  ⚠️ 000001无数据")
        sys.exit(1)
    
    # 转换为Pandas并排序
    df_pd = df_000001.to_pandas().sort_values('trade_date')
    
    print(f"\n[2] 000001的收盘价数据:")
    print(df_pd[['trade_date', 'close']].to_string())
    
    # 手动计算MA5和MA10
    print(f"\n[3] 手动计算MA5和MA10:")
    df_pd['ma5_calc'] = df_pd['close'].rolling(window=5).mean()
    df_pd['ma10_calc'] = df_pd['close'].rolling(window=10).mean()
    
    # 显示2025-01-10到2025-01-20的数据
    df_subset = df_pd[df_pd['trade_date'] >= '2025-01-10'][['trade_date', 'close', 'ma5', 'ma10', 'ma5_calc', 'ma10_calc']]
    print(df_subset.to_string())
    
    # 检查MA值是否匹配
    print(f"\n[4] 检查MA值是否匹配:")
    df_subset['ma5_match'] = np.isclose(df_subset['ma5'], df_subset['ma5_calc'], rtol=1e-5)
    df_subset['ma10_match'] = np.isclose(df_subset['ma10'], df_subset['ma10_calc'], rtol=1e-5)
    
    print(df_subset[['trade_date', 'ma5_match', 'ma10_match']].to_string())
    
    # 检查2025-01-20的金叉条件
    print(f"\n[5] 检查2025-01-20的金叉条件:")
    
    # 找到2025-01-17和2025-01-20的行
    idx_0117 = df_pd[df_pd['trade_date'] == '2025-01-17'].index[0]
    idx_0120 = df_pd[df_pd['trade_date'] == '2025-01-20'].index[0]
    
    ma5_0117 = df_pd.loc[idx_0117, 'ma5_calc']
    ma10_0117 = df_pd.loc[idx_0117, 'ma10_calc']
    ma5_0120 = df_pd.loc[idx_0120, 'ma5_calc']
    ma10_0120 = df_pd.loc[idx_0120, 'ma10_calc']
    
    print(f"  2025-01-17: MA5={ma5_0117:.4f}, MA10={ma10_0117:.4f}, MA5<MA10? {ma5_0117 < ma10_0117}")
    print(f"  2025-01-20: MA5={ma5_0120:.4f}, MA10={ma10_0120:.4f}, MA5>MA10? {ma5_0120 > ma10_0120}")
    print(f"  金叉条件: {ma5_0117 < ma10_0117 and ma5_0120 > ma10_0120}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
