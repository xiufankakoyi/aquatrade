"""
调试信号生成 - 检查为什么2025-01-02没有买入信号
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
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

print("=" * 70)
print("调试信号生成")
print("=" * 70)

try:
    # 初始化
    data_query = OptimizedStockDataQuery()
    strategy = MainWaveTrendStrategy()

    # 获取2025-01-02的数据
    print("\n[1] 获取2025-01-02的市场数据...")
    df = data_query.get_market_data('2025-01-02')
    print(f"  获取到 {len(df)} 只股票")

    # 检查聚宽买入的股票数据
    target_stocks = ['000030', '002626', '002403']
    print(f"\n[2] 检查聚宽买入的股票数据:")
    for code in target_stocks:
        stock_data = df[df['stock_code'] == code]
        if len(stock_data) > 0:
            row = stock_data.iloc[0]
            print(f"\n  {code}:")
            print(f"    收盘价: {row.get('close', 'N/A')}")
            print(f"    MA5: {row.get('ma5', 'N/A')}")
            print(f"    MA10: {row.get('ma10', 'N/A')}")
            print(f"    MA20: {row.get('ma20', 'N/A')}")
            print(f"    量比: {row.get('volume_ratio', 'N/A')}")
            print(f"    总市值: {row.get('total_mv', 'N/A')}")
        else:
            print(f"  {code}: 数据不存在!")

    # 预加载数据
    print("\n[3] 预加载历史数据...")
    preloaded = data_query.preload_data_for_backtest('2025-01-01', '2025-01-31')
    print(f"  预加载完成")

    # 获取交易日列表
    trading_dates = data_query.get_trading_dates('2025-01-01', '2025-01-31')
    print(f"  交易日数量: {len(trading_dates)}")
    print(f"  交易日: {trading_dates[:5]}...")

    # 获取股票列表
    stock_codes = df['stock_code'].unique().tolist()
    print(f"  股票数量: {len(stock_codes)}")

    # 准备价格矩阵
    print("\n[4] 准备价格矩阵...")

    # 获取所需字段
    required_fields = ['open', 'high', 'low', 'close', 'volume', 'amount',
                       'ma5', 'ma10', 'ma20', 'volume_ma5', 'total_mv',
                       'is_st', 'is_kc', 'is_cy']

    T = len(trading_dates)
    N = len(stock_codes)

    print(f"  时间维度 T: {T}")
    print(f"  股票维度 N: {N}")

    # 构建价格矩阵
    price_matrix = {}
    for field in required_fields:
        price_matrix[field] = np.full((T, N), np.nan)

    # 填充数据
    for t, date in enumerate(trading_dates):
        if date in preloaded:
            day_df = preloaded[date]
            for n, code in enumerate(stock_codes):
                stock_data = day_df[day_df['stock_code'] == code]
                if len(stock_data) > 0:
                    for field in required_fields:
                        if field in stock_data.columns:
                            price_matrix[field][t, n] = stock_data[field].iloc[0]

    print(f"  价格矩阵构建完成")

    # 检查2025-01-02的数据 (t=1)
    print("\n[5] 检查2025-01-02的矩阵数据:")
    t_idx = 1  # 2025-01-02
    for code in target_stocks:
        if code in stock_codes:
            n_idx = stock_codes.index(code)
            print(f"\n  {code} (t={t_idx}, n={n_idx}):")
            print(f"    收盘价: {price_matrix['close'][t_idx, n_idx]}")
            print(f"    MA5: {price_matrix['ma5'][t_idx, n_idx]}")
            print(f"    MA10: {price_matrix['ma10'][t_idx, n_idx]}")
            print(f"    MA20: {price_matrix['ma20'][t_idx, n_idx]}")
            print(f"    量比: {price_matrix['volume_ratio'][t_idx, n_idx]}")

    # 生成信号
    print("\n[6] 生成信号...")
    signals = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes,
        data_query=data_query,
        preloaded_data=preloaded
    )

    print(f"  信号矩阵形状: {signals.shape}")
    print(f"  信号矩阵 (2025-01-02):")
    print(f"    买入信号数: {np.sum(signals[1] == 1)}")
    print(f"    卖出信号数: {np.sum(signals[1] == -1)}")
    print(f"    持有信号数: {np.sum(signals[1] == 0)}")

    # 检查聚宽股票的信号
    print(f"\n  聚宽股票的信号 (2025-01-02):")
    for code in target_stocks:
        if code in stock_codes:
            n_idx = stock_codes.index(code)
            signal = signals[1, n_idx]
            print(f"    {code}: {signal} ({'买入' if signal == 1 else '卖出' if signal == -1 else '无'})")

    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
