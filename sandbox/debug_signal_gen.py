"""
调试信号生成
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import numpy as np
import pandas as pd

query = OptimizedStockDataQuery()

strategy = MainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-03'
end_date = '2025-06-10'

# 预加载数据
query.preload_backtest_data(start_date, end_date)
preloaded = getattr(query, '_preloaded_data', None)

if preloaded:
    trading_dates = sorted(preloaded.keys())
    
    # 获取股票代码
    all_codes = set()
    for df in preloaded.values():
        if df is not None and len(df) > 0:
            all_codes.update(df['stock_code'].unique().to_list())
    stock_codes_list = sorted([str(c).zfill(6) for c in all_codes])
    
    # 构建价格矩阵
    T = len(trading_dates)
    N = len(stock_codes_list)
    price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
    
    code_to_idx = {code: i for i, code in enumerate(stock_codes_list)}
    date_to_idx = {date: i for i, date in enumerate(trading_dates)}
    
    for date_str, df_day in preloaded.items():
        if df_day is not None and len(df_day) > 0:
            t_idx = date_to_idx.get(date_str, -1)
            if t_idx >= 0:
                for row in df_day.iter_rows(named=True):
                    code = str(row['stock_code']).zfill(6)
                    n_idx = code_to_idx.get(code, -1)
                    if n_idx >= 0:
                        price_matrix[t_idx, n_idx, 0] = row.get('open', np.nan)
                        price_matrix[t_idx, n_idx, 1] = row.get('high', np.nan)
                        price_matrix[t_idx, n_idx, 2] = row.get('low', np.nan)
                        price_matrix[t_idx, n_idx, 3] = row.get('close', np.nan)
    
    # 生成信号
    print("生成信号...")
    signal_matrix = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes_list,
        data_query=query,
        preloaded_data=preloaded
    )
    
    print(f"\n信号矩阵: {signal_matrix.shape}")
    print(f"买入信号 (1): {np.sum(signal_matrix == 1)}")
    print(f"卖出信号 (2): {np.sum(signal_matrix == 2)}")
    
    # 检查每天的信号
    print(f"\n每日信号统计:")
    for t in range(T):
        buy_count = np.sum(signal_matrix[t] == 1)
        sell_count = np.sum(signal_matrix[t] == 2)
        if buy_count > 0 or sell_count > 0:
            print(f"  {trading_dates[t]}: 买入={buy_count}, 卖出={sell_count}")
    
    # 检查策略保存的 _stock_codes
    print(f"\n策略保存的 _stock_codes (前10个): {strategy._stock_codes[:10]}")
