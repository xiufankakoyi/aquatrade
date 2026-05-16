"""
调试矩阵形状
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 重定向日志到文件
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.FileHandler('c:/Users/Liu/Desktop/projects/aquatrade/sandbox/debug_output.log', 'w')]
)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import pandas as pd
import numpy as np

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-03'
end_date = '2025-06-10'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
trading_dates = [ts.strftime("%Y-%m-%d") for ts in time_series]
T = len(trading_dates)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

# 获取股票代码列表
if preloaded_data and 'stock_daily' in preloaded_data:
    stock_daily = preloaded_data['stock_daily']
    all_codes = stock_daily['stock_code'].unique().to_list()
    stock_codes_list = sorted([str(c).zfill(6) for c in all_codes])
    N = len(stock_codes_list)
    
    print(f"回测参数:")
    print(f"  T (交易日数): {T}")
    print(f"  N (股票数): {N}")
    print(f"  trading_dates: {trading_dates}")
    
    # 检查因子矩阵
    if engine._factor_matrix is not None:
        fm = engine._factor_matrix
        print(f"\n因子矩阵:")
        print(f"  fm.dates: {len(fm.dates)} 天")
        print(f"  fm.codes_str: {len(fm.codes_str)} 只股票")
        print(f"  fm.values shape: {fm.values.shape}")
        
        # 检查条件
        dates_match = len(fm.dates) == T
        codes_match = len(fm.codes_str) == N
        print(f"\n匹配检查:")
        print(f"  len(fm.dates) == T: {dates_match} ({len(fm.dates)} vs {T})")
        print(f"  len(fm.codes_str) == N: {codes_match} ({len(fm.codes_str)} vs {N})")
    
    # 调用 _build_price_matrix_from_cache
    print(f"\n调用 _build_price_matrix_from_cache...")
    price_matrix = engine._build_price_matrix_from_cache(
        preloaded_data, trading_dates, stock_codes_list, T, N
    )
    print(f"price_matrix shape: {price_matrix.shape}")
    print(f"expected shape: ({T}, {N}, 4)")
    
    # 调用策略的向量化信号生成
    print(f"\n调用 generate_signals_vectorized...")
    signal_matrix = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes_list,
        data_query=query,
        preloaded_data=preloaded_data
    )
    print(f"signal_matrix shape: {signal_matrix.shape}")
    print(f"signal_matrix 非零元素数: {np.count_nonzero(signal_matrix)}")
    
    # 检查每天的信号数
    for i, date in enumerate(trading_dates):
        day_signals = signal_matrix[i, :]
        buy_count = np.sum(day_signals == 1)
        sell_count = np.sum(day_signals == 2)
        if buy_count > 0 or sell_count > 0:
            print(f"  {date}: buy={buy_count}, sell={sell_count}")
else:
    print("预加载数据为空！")
