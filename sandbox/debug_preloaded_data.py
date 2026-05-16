"""
调试 preloaded_data 数据结构
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
print("调试 preloaded_data 数据结构")
print("=" * 70)

try:
    # 初始化
    data_query = OptimizedStockDataQuery()
    
    # 获取交易日列表
    trading_dates = data_query.get_trading_dates('2025-01-01', '2025-01-10')  # 只取前10天
    print(f"交易日数量: {len(trading_dates)}")
    print(f"交易日: {trading_dates}")
    
    # 获取第一天的数据
    print("\n[1] 检查第一天的数据...")
    df = data_query.get_market_data('2025-01-02')
    print(f"  数据类型: {type(df)}")
    print(f"  数据形状: {df.shape}")
    print(f"  列名: {list(df.columns)}")
    print(f"  股票数量: {df['stock_code'].nunique()}")
    print(f"  股票代码示例: {df['stock_code'].unique()[:10].tolist()}")
    
    # 检查000001的数据
    stock_data = df[df['stock_code'] == '000001']
    print(f"\n  000001 数据:")
    print(f"    行数: {len(stock_data)}")
    if len(stock_data) > 0:
        row = stock_data.iloc[0]
        print(f"    close: {row.get('close')}")
        print(f"    ma5: {row.get('ma5')}")
        print(f"    ma10: {row.get('ma10')}")
    
    # 检查是否有重复
    print(f"\n[2] 检查重复股票代码...")
    dup_counts = df['stock_code'].value_counts()
    dups = dup_counts[dup_counts > 1]
    if len(dups) > 0:
        print(f"  发现 {len(dups)} 个重复的股票代码")
        print(f"  重复示例: {dups.head().to_dict()}")
    else:
        print(f"  没有发现重复")
    
    # 检查 stock_code 格式
    print(f"\n[3] 检查 stock_code 格式...")
    sample_codes = df['stock_code'].unique()[:20]
    for code in sample_codes:
        print(f"  '{code}' (长度: {len(str(code))})")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
