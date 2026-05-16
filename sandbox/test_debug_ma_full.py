"""
调试完整的MA值和金叉死叉
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import polars as pl
from data_svc.unified_data_manager import get_unified_manager

print("=" * 70)
print("调试完整的MA值和金叉死叉")
print("=" * 70)

try:
    # 读取数据
    print("\n[1] 读取数据...")
    manager = get_unified_manager()
    df = manager.read('stock_daily', start_date='2025-01-01', end_date='2025-01-27', use_cache=False)
    
    if df.is_empty():
        print("  ⚠️ 数据为空")
        sys.exit(1)
    
    # 过滤000001的数据
    df_000001 = df.filter(pl.col('stock_code') == '000001')
    
    if df_000001.is_empty():
        print("  ⚠️ 000001无数据")
        sys.exit(1)
    
    # 按日期排序
    df_000001 = df_000001.sort('trade_date')
    
    print(f"\n[2] 000001在2025-01的数据:")
    print(f"{'日期':<12} {'Close':<10} {'MA5':<10} {'MA10':<10} {'MA5>MA10?':<12}")
    print("-" * 60)
    
    for row in df_000001.iter_rows(named=True):
        date = row['trade_date']
        close = row.get('close', np.nan)
        ma5 = row.get('ma5', np.nan)
        ma10 = row.get('ma10', np.nan)
        
        close_str = f"{close:.2f}" if not np.isnan(close) else "N/A"
        ma5_str = f"{ma5:.4f}" if not np.isnan(ma5) else "N/A"
        ma10_str = f"{ma10:.4f}" if not np.isnan(ma10) else "N/A"
        
        if not np.isnan(ma5) and not np.isnan(ma10):
            cmp = "MA5>MA10" if ma5 > ma10 else ("MA5<MA10" if ma5 < ma10 else "MA5=MA10")
        else:
            cmp = "N/A"
        
        print(f"{date:<12} {close_str:<10} {ma5_str:<10} {ma10_str:<10} {cmp:<12}")
    
    # 手动计算金叉死叉
    print(f"\n[3] 手动计算金叉死叉:")
    
    rows = df_000001.iter_rows(named=True)
    rows_list = list(rows)
    
    signals = []
    for i in range(2, len(rows_list)):
        prev2 = rows_list[i-2]
        prev1 = rows_list[i-1]
        curr = rows_list[i]
        
        prev2_ma5 = prev2.get('ma5', np.nan)
        prev2_ma10 = prev2.get('ma10', np.nan)
        prev1_ma5 = prev1.get('ma5', np.nan)
        prev1_ma10 = prev1.get('ma10', np.nan)
        
        if np.isnan(prev2_ma5) or np.isnan(prev2_ma10) or np.isnan(prev1_ma5) or np.isnan(prev1_ma10):
            continue
        
        date = curr['trade_date']
        
        # 金叉: 前日MA5 < 前日MA10，昨日MA5 > 昨日MA10
        if prev2_ma5 < prev2_ma10 and prev1_ma5 > prev1_ma10:
            signals.append(('金叉', date, prev2['trade_date'], prev1['trade_date'], prev2_ma5, prev2_ma10, prev1_ma5, prev1_ma10))
        
        # 死叉: 前日MA5 > 前日MA10，昨日MA5 < 昨日MA10
        elif prev2_ma5 > prev2_ma10 and prev1_ma5 < prev1_ma10:
            signals.append(('死叉', date, prev2['trade_date'], prev1['trade_date'], prev2_ma5, prev2_ma10, prev1_ma5, prev1_ma10))
    
    if signals:
        for sig_type, date, prev2_date, prev1_date, prev2_ma5, prev2_ma10, prev1_ma5, prev1_ma10 in signals:
            print(f"  ✓ {sig_type} @ {date}")
            print(f"      前日({prev2_date}): MA5={prev2_ma5:.4f}, MA10={prev2_ma10:.4f}")
            print(f"      昨日({prev1_date}): MA5={prev1_ma5:.4f}, MA10={prev1_ma10:.4f}")
    else:
        print("  ⚠️ 没有信号")
    
    print(f"\n[4] 结论:")
    print(f"  2025年1月 {'有' if signals else '没有'} 金叉信号")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
