"""
MA交叉策略回测 - 使用动态复权

核心改进：
1. 指标计算使用前复权价格（price_matrix_adj）
2. 交易执行使用不复权价格（price_matrix）
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


class MACrossStrategyDynamicAdj:
    """MA交叉策略 - 使用动态复权"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_DynamicAdj"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（动态复权）"
        self.ma_fast = None
        self.ma_slow = None
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
        """
        向量化信号生成
        
        Args:
            price_matrix: 不复权价格矩阵 (T, N, 4) - 用于交易执行
            price_matrix_adj: 前复权价格矩阵 (T, N, 4) - 用于指标计算
        """
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        # 使用前复权价格计算指标
        price_matrix_for_indicator = price_matrix_adj if price_matrix_adj is not None else price_matrix
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        # 使用前复权收盘价计算MA
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
        
        # 生成信号
        for t in range(1, T):
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            if t >= 2 and not np.isnan(self.ma_fast[t-2]) and not np.isnan(self.ma_slow[t-2]):
                prev_fast = self.ma_fast[t-1]
                prev_slow = self.ma_slow[t-1]
                prev2_fast = self.ma_fast[t-2]
                prev2_slow = self.ma_slow[t-2]
                
                date = trading_dates[t]
                
                if prev2_fast < prev2_slow and prev_fast > prev_slow:
                    signals[t, n] = 1
                    print(f"[Signal] 金叉 @ {date}")
                elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                    signals[t, n] = -1
                    print(f"[Signal] 死叉 @ {date}")
        
        return signals


print("=" * 70)
print("MA交叉策略回测 - 使用动态复权")
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
    
    strategy = MACrossStrategyDynamicAdj(fast_period=5, slow_period=10)
    
    # 测试包含除权除息的时期
    print("\n[2] 运行回测（2024-06-01 ~ 2024-07-31）...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2024-06-01 ~ 2024-07-31")
    print(f"   初始资金: {config.initial_capital}")
    
    trades = []
    dividends = []
    
    for event in engine.run_backtest('2024-06-01', '2024-07-31', strategy):
        if event['type'] == 'new_trade_engine':
            trade = event['data']
            trades.append(trade)
            if trade['code'] == '000001':
                print(f"[Trade] {trade['date']} {trade['action']:6} {trade['code']} "
                      f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
        elif event['type'] == 'dividend_payout':
            dividends.append(event['data'])
            print(f"[Dividend] {event['data']}")
    
    print("\n[3] 回测结果:")
    print(f"   交易次数: {len(trades)}")
    print(f"   分红/送转: {len(dividends)}次")
    
    if dividends:
        print("\n【分红/送转详情】")
        for div in dividends:
            print(f"   {div}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
