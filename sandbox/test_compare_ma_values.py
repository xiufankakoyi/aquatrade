"""
对比聚宽和AquaTrade的MA值
检查为什么AquaTrade在2025-01-21没有检测到金叉
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 70)
print("对比聚宽和AquaTrade的MA值")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 获取000001的日线数据...")
    data_query = OptimizedStockDataQuery()
    
    # 获取2025年1月的数据
    df = data_query.get_stock_history('000001', '2024-12-01', '2025-02-28')
    
    if df.empty:
        print("  ⚠️ 无数据")
        sys.exit(1)
    
    print(f"  获取到 {len(df)} 条数据")
    print(f"  列: {df.columns.tolist()}")
    
    # 计算MA5和MA10
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    
    # 显示2025年1月的数据
    print("\n[2] 2025年1月的数据:")
    print("=" * 70)
    
    jan_df = df[df['trade_date'] >= '2025-01-01'].copy()
    
    print(f"{'日期':<12} {'收盘价':<8} {'MA5':<8} {'MA10':<8} {'MA5>MA10':<10} {'金叉':<6} {'死叉':<6}")
    print("-" * 70)
    
    for i, row in jan_df.iterrows():
        date = row['trade_date']
        close = row['close']
        ma5 = row['ma5']
        ma10 = row['ma10']
        
        if pd.isna(ma5) or pd.isna(ma10):
            continue
        
        ma5_gt_ma10 = ma5 > ma10
        
        # 检查金叉死叉
        golden_cross = False
        death_cross = False
        if i > 0:
            prev_ma5 = df.iloc[i-1]['ma5']
            prev_ma10 = df.iloc[i-1]['ma10']
            if not pd.isna(prev_ma5) and not pd.isna(prev_ma10):
                golden_cross = (prev_ma5 < prev_ma10) and (ma5 > ma10)
                death_cross = (prev_ma5 > prev_ma10) and (ma5 < ma10)
        
        gc_mark = "✓" if golden_cross else ""
        dc_mark = "✓" if death_cross else ""
        
        print(f"{date:<12} {close:<8.2f} {ma5:<8.2f} {ma10:<8.2f} {str(ma5_gt_ma10):<10} {gc_mark:<6} {dc_mark:<6}")
    
    print("\n[3] 聚宽日志中的MA值 (2025-01-21):")
    print("  聚宽: MA5=11.46, MA10=11.42, 价格=11.42")
    print("  昨日MA5=11.45, 昨日MA10=11.40")
    print("  金叉: MA5(11.46) > MA10(11.42) 且 昨日MA5(11.45) < 昨日MA10(11.40)")
    
    # 检查2025-01-21的数据
    jan_21 = df[df['trade_date'] == '2025-01-21']
    if not jan_21.empty:
        idx = jan_21.index[0]
        print(f"\n[4] AquaTrade数据库中2025-01-21的数据:")
        print(f"  日期: {jan_21.iloc[0]['trade_date']}")
        print(f"  收盘价: {jan_21.iloc[0]['close']}")
        print(f"  MA5: {jan_21.iloc[0]['ma5']:.2f}")
        print(f"  MA10: {jan_21.iloc[0]['ma10']:.2f}")
        
        # 检查前一天
        if idx > 0:
            prev_row = df.iloc[idx-1]
            print(f"\n[5] 前一天(2025-01-20)的数据:")
            print(f"  日期: {prev_row['trade_date']}")
            print(f"  MA5: {prev_row['ma5']:.2f}")
            print(f"  MA10: {prev_row['ma10']:.2f}")
            
            # 判断是否金叉
            is_golden = (prev_row['ma5'] < prev_row['ma10']) and (jan_21.iloc[0]['ma5'] > jan_21.iloc[0]['ma10'])
            print(f"\n[6] 是否金叉: {is_golden}")
    
    print("\n" + "=" * 70)
    print("对比完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
