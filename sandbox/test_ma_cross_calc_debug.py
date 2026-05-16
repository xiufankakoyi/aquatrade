"""
MA交叉策略回测 - 自己计算MA（调试版）
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


class MACrossStrategyCalcDebug:
    """
    MA交叉策略 - 自己计算MA值（调试版）
    """
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_Cross_Calc_Debug"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（自己计算MA-调试版）"
        
        self.ma_fast = None
        self.ma_slow = None
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None
    ) -> np.ndarray:
        """向量化信号生成 - 自己计算MA"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        # 找到000001的索引
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        # 提取收盘价
        close_prices = price_matrix[:, :, 3]
        
        # 自己计算MA
        self.ma_fast = np.full_like(close_prices, np.nan)
        self.ma_slow = np.full_like(close_prices, np.nan)
        
        for n in range(N):
            prices = close_prices[:, n]
            valid_mask = ~np.isnan(prices)
            if np.sum(valid_mask) < self.slow_period:
                continue
            
            prices_valid = prices[valid_mask]
            prices_series = pd.Series(prices_valid)
            ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
            ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
            
            self.ma_fast[valid_mask, n] = ma_fast_series.values
            self.ma_slow[valid_mask, n] = ma_slow_series.values
        
        # 调试：打印000001的MA值
        if self.target_idx is not None:
            print(f"\n[Strategy Debug] 000001的MA值:")
            print(f"{'日期':<12} {'Close':<8} {'MA5':<10} {'MA10':<10} {'MA5>MA10?'}")
            print("-" * 60)
            
            for t in range(T):
                date = trading_dates[t]
                close = close_prices[t, self.target_idx]
                ma5 = self.ma_fast[t, self.target_idx]
                ma10 = self.ma_slow[t, self.target_idx]
                
                if not np.isnan(ma5) and not np.isnan(ma10):
                    cmp = "MA5>MA10" if ma5 > ma10 else ("MA5<MA10" if ma5 < ma10 else "MA5=MA10")
                    print(f"{date:<12} {close:<8.2f} {ma5:<10.4f} {ma10:<10.4f} {cmp}")
        
        # 计算金叉死叉
        signal_count = 0
        for t in range(1, T):
            for n in range(N):
                if np.isnan(self.ma_fast[t-1, n]) or np.isnan(self.ma_slow[t-1, n]):
                    continue
                
                if t >= 2 and not np.isnan(self.ma_fast[t-2, n]) and not np.isnan(self.ma_slow[t-2, n]):
                    prev_fast = self.ma_fast[t-1, n]
                    prev_slow = self.ma_slow[t-1, n]
                    prev2_fast = self.ma_fast[t-2, n]
                    prev2_slow = self.ma_slow[t-2, n]
                    
                    date = trading_dates[t]
                    
                    # 金叉
                    if prev2_fast < prev2_slow and prev_fast > prev_slow:
                        signals[t, n] = 1
                        signal_count += 1
                        if n == self.target_idx:
                            print(f"  ✓ 金叉信号 @ {date}: 前日MA5={prev2_fast:.4f}, 前日MA10={prev2_slow:.4f}, "
                                  f"昨日MA5={prev_fast:.4f}, 昨日MA10={prev_slow:.4f}")
                    
                    # 死叉
                    elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                        signals[t, n] = -1
                        signal_count += 1
                        if n == self.target_idx:
                            print(f"  ✓ 死叉信号 @ {date}: 前日MA5={prev2_fast:.4f}, 前日MA10={prev2_slow:.4f}, "
                                  f"昨日MA5={prev_fast:.4f}, 昨日MA10={prev_slow:.4f}")
        
        print(f"\n[Strategy Debug] 信号总数: {signal_count}")
        
        return signals


print("=" * 70)
print("MA交叉策略回测 - 自己计算MA（调试版）")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyCalcDebug(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    
    results = []
    trades = []
    for event in engine.run_backtest('2025-01-01', '2025-01-31', strategy):
        if event['type'] == 'backtest_complete':
            results.append(event['data'])
        elif event['type'] == 'trade':
            trade = event['data']
            trades.append(trade)
            print(f"   交易: {trade['date']} {trade['action']} {trade['stock_code']} "
                  f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
    
    print("\n[3] 回测结果:")
    if results:
        result = results[-1]
        print(f"   初始资金: {result.get('initial_capital', 100000):.2f}")
        print(f"   最终资金: {result.get('final_value', 0):.2f}")
        print(f"   总收益率: {result.get('total_return', 0):.2%}")
        print(f"   交易次数: {result.get('total_trades', 0)}")
    else:
        print("   无结果")
    
    print(f"\n[4] 交易记录 ({len(trades)}笔):")
    for trade in trades:
        print(f"   {trade['date']} {trade['action']:6} {trade['stock_code']} "
              f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
