"""
检查2025-01-20是否真的出现金叉
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
print("检查2025-01-20金叉条件")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 获取000001的日线数据...")
    data_query = OptimizedStockDataQuery()
    
    # 获取数据
    df = data_query.get_stock_history('000001', '2024-12-01', '2025-02-28')
    
    if df.empty:
        print("  ⚠️ 无数据")
        sys.exit(1)
    
    # 计算MA5和MA10
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    
    # 显示2025年1月15日到1月25日的数据
    print("\n[2] 2025年1月15日-25日的数据:")
    print("=" * 70)
    
    jan_df = df[(df['trade_date'] >= '2025-01-15') & (df['trade_date'] <= '2025-01-25')].copy()
    
    print(f"{'日期':<12} {'收盘价':<8} {'MA5':<8} {'MA10':<8} {'金叉':<6} {'死叉':<6}")
    print("-" * 70)
    
    for i, row in jan_df.iterrows():
        date = row['trade_date']
        close = row['close']
        ma5 = row['ma5']
        ma10 = row['ma10']
        
        if pd.isna(ma5) or pd.isna(ma10):
            print(f"{date:<12} {close:<8.2f} {'N/A':<8} {'N/A':<8}")
            continue
        
        # 检查金叉死叉（需要前一天的数据）
        golden_cross = False
        death_cross = False
        
        # 找到当前行在原始df中的索引
        idx = df[df['trade_date'] == date].index[0]
        if idx > 0:
            prev_row = df.iloc[idx-1]
            if not pd.isna(prev_row['ma5']) and not pd.isna(prev_row['ma10']):
                golden_cross = (prev_row['ma5'] < prev_row['ma10']) and (ma5 > ma10)
                death_cross = (prev_row['ma5'] > prev_row['ma10']) and (ma5 < ma10)
        
        gc_mark = "✓" if golden_cross else ""
        dc_mark = "✓" if death_cross else ""
        
        print(f"{date:<12} {close:<8.2f} {ma5:<8.2f} {ma10:<8.2f} {gc_mark:<6} {dc_mark:<6}")
    
    # 详细检查2025-01-20
    print("\n[3] 详细检查2025-01-20:")
    print("=" * 70)
    
    jan_20 = df[df['trade_date'] == '2025-01-20'].iloc[0]
    jan_17 = df[df['trade_date'] == '2025-01-17'].iloc[0]
    
    print(f"2025-01-17 (前一日):")
    print(f"  MA5: {jan_17['ma5']:.4f}")
    print(f"  MA10: {jan_17['ma10']:.4f}")
    print(f"  MA5 < MA10: {jan_17['ma5'] < jan_17['ma10']}")
    
    print(f"\n2025-01-20 (当日):")
    print(f"  MA5: {jan_20['ma5']:.4f}")
    print(f"  MA10: {jan_20['ma10']:.4f}")
    print(f"  MA5 > MA10: {jan_20['ma5'] > jan_20['ma10']}")
    
    # 判断金叉
    is_golden = (jan_17['ma5'] < jan_17['ma10']) and (jan_20['ma5'] > jan_20['ma10'])
    print(f"\n金叉条件: 前日MA5 < 前日MA10 且 当日MA5 > 当日MA10")
    print(f"结果: {is_golden}")
    
    # 检查聚宽日志中的MA值
    print("\n[4] 聚宽日志中的MA值:")
    print("=" * 70)
    print("聚宽 2025-01-21 日志显示:")
    print("  价格: 11.42")
    print("  MA5: 11.46")
    print("  MA10: 11.42")
    print("  昨日MA5: 11.45")
    print("  昨日MA10: 11.40")
    print("")
    print("分析:")
    print("  聚宽的'昨日MA5=11.45'对应 AquaTrade的2025-01-17 MA5=11.42")
    print("  聚宽的'昨日MA10=11.40'对应 AquaTrade的2025-01-17 MA10=11.42")
    print("  聚宽的'MA5=11.46'对应 AquaTrade的2025-01-20 MA5=11.46")
    print("  聚宽的'MA10=11.42'对应 AquaTrade的2025-01-20 MA10=11.42")
    print("")
    print("结论:")
    print("  聚宽在2025-01-21开盘前，看到的是2025-01-20的数据")
    print("  所以聚宽在2025-01-21买入，是因为2025-01-20出现了金叉")
    print("  金叉条件: 2025-01-17 MA5(11.42) < MA10(11.42)? 否，相等")
    print("  实际上2025-01-20并没有出现金叉！")
    
    print("\n[5] 重新分析:")
    print("=" * 70)
    print("让我们检查2025-01-16到2025-01-20的数据:")
    
    for date in ['2025-01-16', '2025-01-17', '2025-01-20']:
        row = df[df['trade_date'] == date].iloc[0]
        print(f"{date}: MA5={row['ma5']:.4f}, MA10={row['ma10']:.4f}, "
              f"MA5-MA10={row['ma5']-row['ma10']:.4f}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
