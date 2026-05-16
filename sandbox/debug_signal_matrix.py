"""
详细调试信号矩阵
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


class DebugStrategy2:
    """调试策略 - 打印信号矩阵"""
    
    def __init__(self):
        self.name = "Debug2"
        self.description = "调试信号矩阵"
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None,
        price_matrix_adj: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """打印信号矩阵"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        price_matrix_for_indicator = price_matrix_adj if price_matrix_adj is not None else price_matrix
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        close_prices_adj = price_matrix_for_indicator[:, :, 3]
        n = self.target_idx
        prices = close_prices_adj[:, n]
        
        valid_mask = ~np.isnan(prices)
        prices_valid = prices[valid_mask]
        prices_series = pd.Series(prices_valid)
        ma_fast_series = prices_series.rolling(window=5).mean()
        ma_slow_series = prices_series.rolling(window=10).mean()
        
        ma_fast = np.full(T, np.nan)
        ma_slow = np.full(T, np.nan)
        ma_fast[valid_mask] = ma_fast_series.values
        ma_slow[valid_mask] = ma_slow_series.values
        
        # 打印关键日期的MA数据
        print("\n【关键日期MA数据】")
        for t in range(len(trading_dates)):
            date = trading_dates[t]
            if date in ['2025-02-05', '2025-02-06', '2025-02-07', '2025-02-10']:
                print(f"  索引{t}: {date} MA5={ma_fast[t]:.4f} MA10={ma_slow[t]:.4f}")
        
        # 生成信号
        print("\n【信号生成过程】")
        for t in range(1, T - 1):
            if np.isnan(ma_fast[t]) or np.isnan(ma_slow[t]):
                continue
            if np.isnan(ma_fast[t-1]) or np.isnan(ma_slow[t-1]):
                continue
            
            curr_fast = ma_fast[t]
            curr_slow = ma_slow[t]
            prev_fast = ma_fast[t-1]
            prev_slow = ma_slow[t-1]
            
            date = trading_dates[t]
            
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signals[t + 1, n] = 1
                print(f"  金叉 @ {date} (索引{t}): prev_fast={prev_fast:.4f} <= prev_slow={prev_slow:.4f}, curr_fast={curr_fast:.4f} > curr_slow={curr_slow:.4f}")
                print(f"    → 设置 signals[{t+1}] = 1 (日期: {trading_dates[t+1]})")
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signals[t + 1, n] = -1
                print(f"  死叉 @ {date} (索引{t}): prev_fast={prev_fast:.4f} >= prev_slow={prev_slow:.4f}, curr_fast={curr_fast:.4f} < curr_slow={curr_slow:.4f}")
                print(f"    → 设置 signals[{t+1}] = -1 (日期: {trading_dates[t+1]})")
        
        # 打印信号矩阵
        print("\n【信号矩阵（非零信号）】")
        for t in range(len(trading_dates)):
            if signals[t, n] != 0:
                print(f"  索引{t}: {trading_dates[t]} 信号={signals[t, n]} ({'买入' if signals[t, n]==1 else '卖出'})")
        
        return signals


print("=" * 70)
print("详细调试信号矩阵")
print("=" * 70)

try:
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = DebugStrategy2()
    
    for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
        if event['type'] == 'new_trade_engine':
            trade = event['data']
            if trade['code'] == '000001':
                print(f"\n[Trade] {trade['date']} {trade['action']} {trade['code']}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
