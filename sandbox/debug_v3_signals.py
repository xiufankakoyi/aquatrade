"""
调试 V3 策略信号生成
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def debug_v3_signals():
    print("=" * 80)
    print("调试 V3 策略信号生成")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    data_query.preload_backtest_data(start_date, end_date)
    preloaded = getattr(data_query, '_preloaded_data', None)
    
    if preloaded is None:
        print("预加载数据为空")
        return
    
    trading_dates = sorted(preloaded.keys())
    stock_codes = sorted(list(set(
        code for df in preloaded.values() 
        for code in df['stock_code'].unique()
    )))
    
    T = len(trading_dates)
    N = len(stock_codes)
    
    print(f"\n交易日数: {T}")
    print(f"股票数: {N}")
    print(f"交易日期: {trading_dates}")
    
    strategy = TrendFollowStrategyV3()
    
    price_matrix = np.zeros((T, N, 4), dtype=np.float32)
    
    signal_matrix = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes,
        data_query=data_query,
        preloaded_data=preloaded
    )
    
    print(f"\n信号矩阵形状: {signal_matrix.shape}")
    print(f"买入信号数: {np.sum(signal_matrix == 1)}")
    print(f"卖出信号数: {np.sum(signal_matrix == -1)}")
    print(f"无操作信号数: {np.sum(signal_matrix == 0)}")
    
    buy_indices = np.where(signal_matrix == 1)
    if len(buy_indices[0]) > 0:
        print(f"\n买入信号示例:")
        for i in range(min(5, len(buy_indices[0]))):
            t_idx = buy_indices[0][i]
            n_idx = buy_indices[1][i]
            print(f"  日期: {trading_dates[t_idx]}, 股票: {stock_codes[n_idx]}")
    
    print(f"\n数据检查:")
    print(f"  close 有效值: {np.sum(np.isfinite(strategy.close))}")
    print(f"  ma5 有效值: {np.sum(np.isfinite(strategy.ma5))}")
    print(f"  ma10 有效值: {np.sum(np.isfinite(strategy.ma10))}")
    print(f"  ma20 有效值: {np.sum(np.isfinite(strategy.ma20))}")


if __name__ == "__main__":
    debug_v3_signals()
