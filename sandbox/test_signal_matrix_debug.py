"""
调试信号矩阵日期映射
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.vectorized_base import VectorizedStrategyBase


class MACrossStrategyDebug(VectorizedStrategyBase):
    """简单均线金叉死叉策略 - 调试版"""
    
    def __init__(self, stock_code='000001'):
        super().__init__()
        self.target_stock = stock_code
        
    def generate_signals_vectorized(
        self,
        price_matrix,
        trading_dates: list,
        stock_codes: list,
        data_query,
        preloaded_data=None
    ) -> np.ndarray:
        """生成交易信号 - 调试版"""
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        print(f"\n[Strategy] generate_signals_vectorized 被调用")
        print(f"   trading_dates: {len(trading_dates)} 天")
        print(f"   范围: {trading_dates[0]} ~ {trading_dates[-1]}")
        print(f"   stock_codes: {len(stock_codes)} 只")
        
        if self.target_stock not in stock_codes:
            print(f"   ⚠️ 目标股票 {self.target_stock} 不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            print(f"   ⚠️ MA数据为空")
            return signals
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        print(f"   ma5_stock形状: {ma5_stock.shape}")
        print(f"   ma5_stock前5个值: {ma5_stock[:5]}")
        print(f"   ma10_stock前5个值: {ma10_stock[:5]}")
        
        # 计算金叉死叉
        signal_count = 0
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                signal_count += 1
                print(f"   [Signal] {trading_dates[t]}: 金叉买入信号 (t={t})")
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                signal_count += 1
                print(f"   [Signal] {trading_dates[t]}: 死叉卖出信号 (t={t})")
        
        print(f"   总共生成 {signal_count} 个信号")
        return signals


print("=" * 70)
print("信号矩阵日期映射调试")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测
    print("\n[2] 运行回测...")
    start_date = '2025-01-01'
    end_date = '2025-02-28'
    
    # 只运行前几天来调试
    events = []
    for i, event in enumerate(engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy
    )):
        events.append(event)
        if i >= 5:  # 只取前几个事件
            break
    
    print(f"\n[3] 检查引擎状态...")
    
    # 检查 _date_to_idx
    if hasattr(engine, '_date_to_idx'):
        print(f"\n   _date_to_idx 映射 (前10个):")
        for i, (date, idx) in enumerate(list(engine._date_to_idx.items())[:10]):
            print(f"      {date} -> {idx}")
    
    # 检查 _backtest_dates
    if hasattr(engine, '_backtest_dates'):
        print(f"\n   _backtest_dates (前10个):")
        for date in sorted(list(engine._backtest_dates))[:10]:
            print(f"      {date}")
    
    # 检查 _signal_matrix
    if hasattr(engine, '_signal_matrix') and engine._signal_matrix is not None:
        print(f"\n   _signal_matrix 形状: {engine._signal_matrix.shape}")
        
        # 检查特定日期的信号
        test_dates = ['2025-01-02', '2025-01-23', '2025-01-24']
        for date_str in test_dates:
            t_idx = engine._date_to_idx.get(date_str, -1)
            if t_idx >= 0 and t_idx < engine._signal_matrix.shape[0]:
                day_signals = engine._signal_matrix[t_idx, :]
                non_zero = np.where(day_signals != 0)[0]
                if len(non_zero) > 0:
                    print(f"   {date_str} (t={t_idx}): 信号={day_signals[non_zero]}, 股票索引={non_zero}")
                else:
                    print(f"   {date_str} (t={t_idx}): 无信号")
            else:
                print(f"   {date_str}: 不在信号矩阵中 (t_idx={t_idx})")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
