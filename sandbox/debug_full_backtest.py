"""
完整调试回测流程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
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

# 手动运行回测的前几步来调试
print("=" * 60)
print("调试回测流程")
print("=" * 60)

# 1. 预加载数据
from datetime import datetime
start_date = '2025-06-01'
end_date = '2025-06-30'

print(f"\n1. 预加载数据: {start_date} ~ {end_date}")
query.preload_backtest_data(start_date, end_date)
preloaded = getattr(query, '_preloaded_data', None)
print(f"   预加载结果: {len(preloaded) if preloaded else 0} 个日期")

# 2. 检查策略信号生成
if preloaded:
    print(f"\n2. 检查策略信号生成")
    
    # 获取交易日期和股票代码
    trading_dates = sorted(preloaded.keys())
    all_codes = set()
    for df in preloaded.values():
        if df is not None and len(df) > 0:
            all_codes.update(df['stock_code'].unique().to_list())
    stock_codes_list = sorted([str(c).zfill(6) for c in all_codes])
    
    print(f"   交易日期: {len(trading_dates)} 天")
    print(f"   股票数量: {len(stock_codes_list)}")
    
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
    
    print(f"   价格矩阵: {price_matrix.shape}")
    print(f"   非NaN close数量: {np.sum(~np.isnan(price_matrix[:, :, 3]))}")
    
    # 调用策略生成信号
    print(f"\n3. 生成信号...")
    signal_matrix = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes_list,
        data_query=query,
        preloaded_data=preloaded
    )
    
    print(f"   信号矩阵: {signal_matrix.shape}")
    print(f"   买入信号 (1): {np.sum(signal_matrix == 1)}")
    print(f"   卖出信号 (2): {np.sum(signal_matrix == 2)}")
    
    # 检查每天的信号
    print(f"\n4. 每日信号统计:")
    for t in range(min(10, T)):
        buy_count = np.sum(signal_matrix[t] == 1)
        sell_count = np.sum(signal_matrix[t] == 2)
        if buy_count > 0 or sell_count > 0:
            print(f"   {trading_dates[t]}: 买入={buy_count}, 卖出={sell_count}")
