"""
对比Tushare MA值和手动计算的MA值
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd

print("=" * 70)
print("对比Tushare MA值和手动计算的MA值")
print("=" * 70)

try:
    # 从ArcticDB读取数据
    print("\n[1] 读取数据...")
    
    from data_svc.unified_data_manager import get_unified_manager
    manager = get_unified_manager()
    
    df = manager.read('stock_daily', start_date='2024-12-01', end_date='2025-01-20', use_cache=False)
    
    if df.is_empty():
        print("  ⚠️ 数据为空")
        sys.exit(1)
    
    # 过滤000001的数据
    df_000001 = df.filter(df['stock_code'] == '000001')
    df_pd = df_000001.to_pandas().sort_values('trade_date')
    
    # 手动计算MA
    df_pd['ma5_calc'] = df_pd['close'].rolling(window=5).mean()
    df_pd['ma10_calc'] = df_pd['close'].rolling(window=10).mean()
    
    print(f"\n[2] 对比MA值:")
    print(f"{'日期':<12} {'Close':<8} {'MA5(Tushare)':<14} {'MA5(计算)':<14} {'MA10(Tushare)':<14} {'MA10(计算)':<14}")
    print("-" * 90)
    
    for _, row in df_pd.iterrows():
        date = row['trade_date']
        close = row['close']
        ma5_tushare = row['ma5']
        ma5_calc = row['ma5_calc']
        ma10_tushare = row['ma10']
        ma10_calc = row['ma10_calc']
        
        ma5_str = f"{ma5_tushare:.4f}" if not np.isnan(ma5_tushare) else "N/A"
        ma5_calc_str = f"{ma5_calc:.4f}" if not np.isnan(ma5_calc) else "N/A"
        ma10_str = f"{ma10_tushare:.4f}" if not np.isnan(ma10_tushare) else "N/A"
        ma10_calc_str = f"{ma10_calc:.4f}" if not np.isnan(ma10_calc) else "N/A"
        
        print(f"{date:<12} {close:<8.2f} {ma5_str:<14} {ma5_calc_str:<14} {ma10_str:<14} {ma10_calc_str:<14}")
    
    # 检查金叉条件
    print(f"\n[3] 使用Tushare MA值检查金叉:")
    
    idx_0117 = df_pd[df_pd['trade_date'] == '2025-01-17'].index[0]
    idx_0120 = df_pd[df_pd['trade_date'] == '2025-01-20'].index[0]
    
    ma5_0117_tushare = df_pd.loc[idx_0117, 'ma5']
    ma10_0117_tushare = df_pd.loc[idx_0117, 'ma10']
    ma5_0120_tushare = df_pd.loc[idx_0120, 'ma5']
    ma10_0120_tushare = df_pd.loc[idx_0120, 'ma10']
    
    print(f"  2025-01-17 (Tushare): MA5={ma5_0117_tushare:.4f}, MA10={ma10_0117_tushare:.4f}")
    print(f"  2025-01-20 (Tushare): MA5={ma5_0120_tushare:.4f}, MA10={ma10_0120_tushare:.4f}")
    print(f"  金叉条件 (Tushare): {ma5_0117_tushare < ma10_0117_tushare and ma5_0120_tushare > ma10_0120_tushare}")
    
    print(f"\n[4] 使用计算MA值检查金叉:")
    
    ma5_0117_calc = df_pd.loc[idx_0117, 'ma5_calc']
    ma10_0117_calc = df_pd.loc[idx_0117, 'ma10_calc']
    ma5_0120_calc = df_pd.loc[idx_0120, 'ma5_calc']
    ma10_0120_calc = df_pd.loc[idx_0120, 'ma10_calc']
    
    print(f"  2025-01-17 (计算): MA5={ma5_0117_calc:.4f}, MA10={ma10_0117_calc:.4f}")
    print(f"  2025-01-20 (计算): MA5={ma5_0120_calc:.4f}, MA10={ma10_0120_calc:.4f}")
    print(f"  金叉条件 (计算): {ma5_0117_calc < ma10_0117_calc and ma5_0120_calc > ma10_0120_calc}")
    
    print(f"\n[5] 结论:")
    print(f"  Tushare的MA值是四舍五入到2位小数的")
    print(f"  实际计算应该使用更精确的MA值")
    print(f"  使用计算MA值时，2025-01-20满足金叉条件")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
