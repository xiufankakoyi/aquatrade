"""
检查信号执行日期
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


class DebugMACrossStrategy:
    """MA交叉策略 - 调试版"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_Debug"
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
        """向量化信号生成 - 调试版"""
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
        if np.sum(valid_mask) < self.slow_period:
            return signals
        
        prices_valid = prices[valid_mask]
        prices_series = pd.Series(prices_valid)
        ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
        ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
        
        ma_fast = np.full(T, np.nan)
        ma_slow = np.full(T, np.nan)
        ma_fast[valid_mask] = ma_fast_series.values
        ma_slow[valid_mask] = ma_slow_series.values
        
        print(f"\n【信号生成 - 调试】")
        print(f"  trading_dates 长度: {len(trading_dates)}")
        print(f"  2025-02-05 索引: {trading_dates.index('2025-02-05') if '2025-02-05' in trading_dates else -1}")
        print(f"  2025-02-07 索引: {trading_dates.index('2025-02-07') if '2025-02-07' in trading_dates else -1}")
        print(f"  2025-02-10 索引: {trading_dates.index('2025-02-10') if '2025-02-10' in trading_dates else -1}")
        
        for t in range(1, T - 1):
            if np.isnan(ma_fast[t]) or np.isnan(ma_slow[t]):
                continue
            if np.isnan(ma_fast[t-1]) or np.isnan(ma_slow[t-1]):
                continue
            
            curr_fast = ma_fast[t]
            curr_slow = ma_slow[t]
            prev_fast = ma_fast[t-1]
            prev_slow = ma_slow[t-1]
            
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signals[t + 1, n] = 1
                if '2025-02-05' <= trading_dates[t] <= '2025-02-15':
                    print(f"  金叉 @ 索引{t} ({trading_dates[t]}): signals[{t+1}] = 1 ({trading_dates[t+1]})")
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signals[t + 1, n] = -1
                if '2025-02-05' <= trading_dates[t] <= '2025-02-15':
                    print(f"  死叉 @ 索引{t} ({trading_dates[t]}): signals[{t+1}] = -1 ({trading_dates[t+1]})")
        
        return signals


print("=" * 70)
print("信号执行调试")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = DebugMACrossStrategy(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2025-02-28")
    
    trades = []
    
    for event in engine.run_backtest('2025-01-01', '2025-02-28', strategy):
        if event['type'] == 'new_trade_engine':
            trade = event['data']
            trades.append(trade)
            print(f"[Trade] {trade['date']} {trade['action']:6} {trade['code']} "
                  f"价格:{trade['price']:.2f}")
    
    print("\n【交易记录汇总】")
    for trade in trades:
        print(f"  {trade['date']}: {trade['action']} @ {trade['price']:.2f}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
