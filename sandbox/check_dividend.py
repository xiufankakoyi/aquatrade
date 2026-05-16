"""
检查分红事件
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.vectorized_base import VectorizedStrategyBase
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


class SimpleMACrossStrategy(VectorizedStrategyBase):
    def __init__(self, fast_period: int = 5, slow_period: int = 10):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.target_idx = None
        self.ma_fast = None
        self.ma_slow = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        price_matrix_adj: np.ndarray,
        trading_dates: list,
        stock_codes: list,
        **kwargs
    ) -> np.ndarray:
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.float32)
        
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
        
        self.ma_fast = np.full(T, np.nan)
        self.ma_slow = np.full(T, np.nan)
        self.ma_fast[valid_mask] = ma_fast_series.values
        self.ma_slow[valid_mask] = ma_slow_series.values
        
        for t in range(1, T - 1):
            if np.isnan(self.ma_fast[t]) or np.isnan(self.ma_slow[t]):
                continue
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            curr_fast = self.ma_fast[t]
            curr_slow = self.ma_slow[t]
            prev_fast = self.ma_fast[t-1]
            prev_slow = self.ma_slow[t-1]
            
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signals[t+1, n] = 1.0
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signals[t+1, n] = -1.0
        
        return signals


print("=" * 70)
print("检查分红事件")
print("=" * 70)

data_query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=100000,
    commission_rate=0.0003,
    warmup_days=30,
    position_ratio=0.9
)
engine = UnifiedBacktestEngine(data_query, config=config)

strategy = SimpleMACrossStrategy(fast_period=5, slow_period=10)

trades = []
dividends = []
daily_cash = []
final_result = None

for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
    if event['type'] == 'new_trade_engine':
        trade = event['data']
        trades.append(trade)
    elif event['type'] == 'dividend_payout':
        dividends.append(event['data'])
        print(f"[分红] {event['data']}")
    elif event['type'] == 'daily_equity_engine':
        daily_cash.append({
            'date': event['data']['date'],
            'equity': event['data']['equity']
        })
    elif event['type'] == 'stream_complete':
        final_result = event['data']

print(f"\n【分红事件】")
for div in dividends:
    print(f"  {div}")

print(f"\n【分红总额】")
total_dividend = sum(d.get('dividend', 0) for d in dividends)
print(f"  总分红: {total_dividend:.2f}")
