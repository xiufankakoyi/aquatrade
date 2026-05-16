"""
MA交叉策略回测 - 调试日期映射
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


class MACrossStrategyCalc:
    """MA交叉策略 - 只交易000001"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_Cross_000001"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（只交易000001）"
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
        """向量化信号生成 - 只生成000001的信号"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        # 找到000001的索引
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            print("[Strategy] 警告: 未找到000001")
            return signals
        
        print(f"\n[Strategy] 信号矩阵形状: {signals.shape}")
        print(f"[Strategy] 交易日期范围: {trading_dates[0]} ~ {trading_dates[-1]}")
        print(f"[Strategy] 总交易日数: {len(trading_dates)}")
        print(f"[Strategy] 000001索引: {self.target_idx}")
        
        # 提取收盘价
        close_prices = price_matrix[:, :, 3]
        
        # 只计算000001的MA
        n = self.target_idx
        prices = close_prices[:, n]
        
        valid_mask = ~np.isnan(prices)
        if np.sum(valid_mask) < self.slow_period:
            print("[Strategy] 警告: 000001数据不足")
            return signals
        
        # 计算MA5和MA10
        prices_valid = prices[valid_mask]
        prices_series = pd.Series(prices_valid)
        ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
        ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
        
        self.ma_fast = np.full(T, np.nan)
        self.ma_slow = np.full(T, np.nan)
        self.ma_fast[valid_mask] = ma_fast_series.values
        self.ma_slow[valid_mask] = ma_slow_series.values
        
        # 计算金叉死叉 - 只针对000001
        for t in range(1, T):
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            if t >= 2 and not np.isnan(self.ma_fast[t-2]) and not np.isnan(self.ma_slow[t-2]):
                prev_fast = self.ma_fast[t-1]
                prev_slow = self.ma_slow[t-1]
                prev2_fast = self.ma_fast[t-2]
                prev2_slow = self.ma_slow[t-2]
                
                date = trading_dates[t]
                
                # 金叉
                if prev2_fast < prev2_slow and prev_fast > prev_slow:
                    signals[t, n] = 1
                    print(f"[Signal] 金叉 @ t={t}, 日期={date}")
                
                # 死叉
                elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                    signals[t, n] = -1
                    print(f"[Signal] 死叉 @ t={t}, 日期={date}")
        
        # 打印信号矩阵中000001的所有非零信号
        print(f"\n[Strategy] 000001的所有信号:")
        for t in range(T):
            if signals[t, n] != 0:
                print(f"  t={t}, 日期={trading_dates[t]}, 信号={signals[t, n]}")
        
        return signals


# 创建一个包装器来追踪信号获取
class DebugBacktestEngine(UnifiedBacktestEngine):
    def _get_vectorized_signals_for_day(self, current_time):
        """包装信号获取以添加调试信息"""
        date_str = current_time.strftime("%Y-%m-%d")
        
        # 调用父类方法
        signals = super()._get_vectorized_signals_for_day(current_time)
        
        # 调试信息
        if '000001' in signals:
            print(f"[GetSignal] {date_str}: 000001信号 = {signals['000001']}")
        
        # 检查日期映射
        if hasattr(self, '_date_to_idx') and hasattr(self, '_signal_matrix'):
            t_idx = self._date_to_idx.get(date_str, -1)
            if t_idx >= 0 and t_idx < self._signal_matrix.shape[0]:
                # 找到000001的索引
                stock_idx = None
                for i, code in enumerate(self._stock_codes_list):
                    if code == '000001':
                        stock_idx = i
                        break
                
                if stock_idx is not None:
                    signal_value = self._signal_matrix[t_idx, stock_idx]
                    print(f"[GetSignal] {date_str}: t_idx={t_idx}, stock_idx={stock_idx}, 原始信号={signal_value}")
        
        return signals


print("=" * 70)
print("MA交叉策略回测 - 调试日期映射")
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
    engine = DebugBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyCalc(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    
    results = []
    trades = []
    
    for event in engine.run_backtest('2025-01-01', '2025-01-31', strategy):
        if event['type'] == 'backtest_complete':
            results.append(event['data'])
        elif event['type'] == 'trade':
            trade = event['data']
            trades.append(trade)
            print(f"[Trade] {trade['date']} {trade['action']:6} {trade['stock_code']}")
    
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
        print(f"   {trade['date']} {trade['action']:6} {trade['stock_code']}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
