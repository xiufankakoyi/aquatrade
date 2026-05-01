"""
调试MA数据加载
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
print("调试MA数据加载")
print("=" * 70)

try:
    # 初始化
    data_query = OptimizedStockDataQuery()
    
    # 获取交易日列表
    trading_dates = data_query.get_trading_dates('2025-01-01', '2026-01-01')
    print(f"交易日数量: {len(trading_dates)}")
    print(f"前5个交易日: {trading_dates[:5]}")
    
    # 获取2025-01-02的数据
    print("\n[1] 检查2025-01-02的数据...")
    df = data_query.get_market_data('2025-01-02')
    print(f"  获取到 {len(df)} 只股票")
    print(f"  列名: {list(df.columns)}")
    
    # 检查000001的数据
    stock_data = df[df['stock_code'] == '000001']
    if len(stock_data) > 0:
        row = stock_data.iloc[0]
        print(f"\n  000001 (平安银行) 数据:")
        for col in ['close', 'ma5', 'ma10', 'ma20', 'volume_ratio']:
            if col in stock_data.columns:
                print(f"    {col}: {row.get(col, 'N/A')}")
    
    # 检查多天的数据
    print("\n[2] 检查000001的多天MA数据...")
    dates_to_check = trading_dates[:10]  # 前10个交易日
    
    ma_data = []
    for date in dates_to_check:
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
    
    # 显示MA数据
    print(f"\n  000001 MA数据 (前10个交易日):")
    print(f"  {'日期':<12} {'收盘价':<10} {'MA5':<10} {'MA10':<10} {'MA20':<10} {'金叉':<6} {'死叉':<6}")
    print("  " + "-" * 70)
    
    for i, d in enumerate(ma_data):
        golden_cross = ""
        death_cross = ""
        if i > 0:
            prev = ma_data[i-1]
            if not pd.isna(d['ma5']) and not pd.isna(d['ma10']) and not pd.isna(prev['ma5']) and not pd.isna(prev['ma10']):
                if prev['ma5'] < prev['ma10'] and d['ma5'] > d['ma10']:
                    golden_cross = "✓金叉"
                elif prev['ma5'] > prev['ma10'] and d['ma5'] < d['ma10']:
                    death_cross = "✓死叉"
        
        print(f"  {d['date']:<12} {d['close']:<10.2f} {d['ma5']:<10.2f} {d['ma10']:<10.2f} {d['ma20']:<10.2f} {golden_cross:<6} {death_cross:<6}")
    
    # 统计金叉死叉
    golden_crosses = []
    death_crosses = []
    
    for i in range(1, len(ma_data)):
        prev = ma_data[i-1]
        curr = ma_data[i]
        if not pd.isna(curr['ma5']) and not pd.isna(curr['ma10']) and not pd.isna(prev['ma5']) and not pd.isna(prev['ma10']):
            if prev['ma5'] < prev['ma10'] and curr['ma5'] > curr['ma10']:
                golden_crosses.append(curr['date'])
            elif prev['ma5'] > prev['ma10'] and curr['ma5'] < curr['ma10']:
                death_crosses.append(curr['date'])
    
    print(f"\n  金叉日期: {golden_crosses}")
    print(f"  死叉日期: {death_crosses}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
