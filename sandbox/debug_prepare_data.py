"""
调试 prepare_data 方法
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
from core.strategies.vectorized_base import VectorizedStrategyBase

print("=" * 70)
print("调试 prepare_data 方法")
print("=" * 70)

try:
    # 初始化
    data_query = OptimizedStockDataQuery()
    
    # 获取交易日列表
    trading_dates = data_query.get_trading_dates('2025-01-01', '2025-01-10')
    print(f"交易日数量: {len(trading_dates)}")
    print(f"交易日: {trading_dates}")
    
    # 模拟 preloaded_data
    print("\n[1] 构建 preloaded_data...")
    preloaded_data = {}
    for date in trading_dates:
        df = data_query.get_market_data(date)
        preloaded_data[date] = df
        print(f"  {date}: {len(df)} 行, 类型: {type(df).__name__}")
    
    # 检查第一天的数据
    first_df = preloaded_data[trading_dates[0]]
    print(f"\n[2] 第一天数据详情:")
    print(f"  列名: {list(first_df.columns)}")
    print(f"  股票数量: {first_df['stock_code'].nunique()}")
    
    # 检查000001的数据
    stock_data = first_df[first_df['stock_code'] == '000001']
    print(f"\n  000001 数据:")
    if len(stock_data) > 0:
        row = stock_data.iloc[0]
        print(f"    close: {row.get('close')}")
        print(f"    ma5: {row.get('ma5')}")
        print(f"    ma10: {row.get('ma10')}")
    
    # 获取股票列表
    stock_codes = first_df['stock_code'].unique().tolist()
    print(f"\n[3] 股票列表:")
    print(f"  总数: {len(stock_codes)}")
    print(f"  前10个: {stock_codes[:10]}")
    
    # 检查是否有重复
    print(f"\n[4] 检查重复:")
    print(f"  唯一股票数: {len(set(stock_codes))}")
    print(f"  列表长度: {len(stock_codes)}")
    if len(set(stock_codes)) != len(stock_codes):
        from collections import Counter
        counts = Counter(stock_codes)
        dups = {k: v for k, v in counts.items() if v > 1}
        print(f"  重复的股票: {dups}")
    
    # 创建策略并调用 prepare_data
    print(f"\n[5] 调用 prepare_data...")
    strategy = VectorizedStrategyBase()
    strategy.prepare_data(preloaded_data, trading_dates, stock_codes)
    
    # 检查MA数据
    print(f"\n[6] 检查MA数据:")
    print(f"  ma5 shape: {strategy.ma5.shape}")
    print(f"  ma10 shape: {strategy.ma10.shape}")
    
    # 找到000001的索引
    if '000001' in stock_codes:
        n_idx = stock_codes.index('000001')
        print(f"\n  000001 索引: {n_idx}")
        print(f"  MA5: {strategy.ma5[:, n_idx]}")
        print(f"  MA10: {strategy.ma10[:, n_idx]}")
        print(f"  MA5 NaN数量: {np.sum(np.isnan(strategy.ma5[:, n_idx]))}")
        print(f"  MA10 NaN数量: {np.sum(np.isnan(strategy.ma10[:, n_idx]))}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
