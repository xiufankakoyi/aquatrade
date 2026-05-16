"""
调试MA数据加载 - 检查全年数据
"""
import os
import sys
import pandas as pd
import numpy as np

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 70)
print("调试MA数据加载 - 全年数据")
print("=" * 70)

try:
    # 初始化
    data_query = OptimizedStockDataQuery()
    
    # 获取交易日列表
    trading_dates = data_query.get_trading_dates('2025-01-01', '2026-01-01')
    print(f"交易日数量: {len(trading_dates)}")
    
    # 检查全年的数据
    print("\n[1] 检查000001的全年MA数据...")
    
    ma_data = []
    for date in trading_dates:
        df = data_query.get_market_data(date)
        stock_data = df[df['stock_code'] == '000001']
        if len(stock_data) > 0:
            row = stock_data.iloc[0]
            ma_data.append({
                'date': date,
                'close': row.get('close'),
                'ma5': row.get('ma5'),
                'ma10': row.get('ma10'),
                'ma20': row.get('ma20')
            })
    
    print(f"  获取到 {len(ma_data)} 天的数据")
    
    # 统计金叉死叉
    golden_crosses = []
    death_crosses = []
    
    for i in range(1, len(ma_data)):
        prev = ma_data[i-1]
        curr = ma_data[i]
        if not pd.isna(curr['ma5']) and not pd.isna(curr['ma10']) and not pd.isna(prev['ma5']) and not pd.isna(prev['ma10']):
            if prev['ma5'] < prev['ma10'] and curr['ma5'] > curr['ma10']:
                golden_crosses.append({
                    'date': curr['date'],
                    'ma5': curr['ma5'],
                    'ma10': curr['ma10'],
                    'close': curr['close']
                })
            elif prev['ma5'] > prev['ma10'] and curr['ma5'] < curr['ma10']:
                death_crosses.append({
                    'date': curr['date'],
                    'ma5': curr['ma5'],
                    'ma10': curr['ma10'],
                    'close': curr['close']
                })
    
    print(f"\n  全年金叉次数: {len(golden_crosses)}")
    for gc in golden_crosses[:5]:  # 显示前5个
        print(f"    {gc['date']}: MA5={gc['ma5']:.2f}, MA10={gc['ma10']:.2f}, 收盘价={gc['close']:.2f}")
    if len(golden_crosses) > 5:
        print(f"    ... 还有 {len(golden_crosses)-5} 个")
    
    print(f"\n  全年死叉次数: {len(death_crosses)}")
    for dc in death_crosses[:5]:  # 显示前5个
        print(f"    {dc['date']}: MA5={dc['ma5']:.2f}, MA10={dc['ma10']:.2f}, 收盘价={dc['close']:.2f}")
    if len(death_crosses) > 5:
        print(f"    ... 还有 {len(death_crosses)-5} 个")
    
    # 显示MA趋势
    print(f"\n[2] MA趋势分析...")
    if len(ma_data) > 0:
        first = ma_data[0]
        last = ma_data[-1]
        print(f"  年初: MA5={first['ma5']:.2f}, MA10={first['ma10']:.2f}")
        print(f"  年末: MA5={last['ma5']:.2f}, MA10={last['ma10']:.2f}")
        
        # 计算MA5 > MA10 的天数比例
        ma5_gt_ma10 = sum(1 for d in ma_data if not pd.isna(d['ma5']) and not pd.isna(d['ma10']) and d['ma5'] > d['ma10'])
        valid_days = sum(1 for d in ma_data if not pd.isna(d['ma5']) and not pd.isna(d['ma10']))
        print(f"  MA5 > MA10 的天数: {ma5_gt_ma10}/{valid_days} ({ma5_gt_ma10/valid_days*100:.1f}%)")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
