"""
MA金叉死叉策略测试 - 调试版9
检查因子矩阵的日期范围
"""
import os
import sys
import pandas as pd
import numpy as np

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.vectorized_base import VectorizedStrategyBase


class MACrossStrategyDebug(VectorizedStrategyBase):
    """简单均线金叉死叉策略 - 调试版"""
    
    strategy_id = "ma_cross_debug"
    strategy_name = "MA金叉死叉策略-调试版"
    
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
        """生成交易信号"""
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_stock not in stock_codes:
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            return signals
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        # 计算金叉死叉 - 只处理2025年的信号
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            if not current_date.startswith('2025'):
                continue
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("MA金叉死叉策略测试 - 调试版9")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测（只运行几天来初始化）
    print("\n[2] 运行回测初始化...")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-10")
    print("=" * 70)
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-10',
        strategy=strategy
    ):
        pass  # 只运行初始化
    
    # 检查因子矩阵
    print("\n" + "=" * 70)
    print("检查因子矩阵的日期范围")
    print("=" * 70)
    
    if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
        fm = engine._factor_matrix
        
        print(f"\n因子矩阵形状: {fm.values.shape}")
        print(f"因子矩阵日期数量: {len(fm.dates)}")
        print(f"因子矩阵日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
        print(f"\n因子矩阵前10个日期: {fm.dates[:10]}")
        print(f"因子矩阵后10个日期: {fm.dates[-10:]}")
        
        print(f"\n因子矩阵 date_to_idx 样本:")
        sample_dates = ['2025-01-02', '2025-01-23', '2025-04-17']
        for d in sample_dates:
            idx = fm.date_to_idx.get(d, 'NOT FOUND')
            print(f"  {d} -> {idx}")
    else:
        print("因子矩阵未初始化!")
    
    # 检查 _date_to_idx
    print("\n" + "=" * 70)
    print("检查引擎 _date_to_idx")
    print("=" * 70)
    
    if hasattr(engine, '_date_to_idx'):
        date_to_idx = engine._date_to_idx
        print(f"\n引擎 _date_to_idx 样本:")
        sample_dates = ['2025-01-02', '2025-01-23', '2025-04-17']
        for d in sample_dates:
            idx = date_to_idx.get(d, 'NOT FOUND')
            print(f"  {d} -> {idx}")
        
        print(f"\n引擎 _date_to_idx 日期数量: {len(date_to_idx)}")
    
    # 检查 _backtest_dates
    print("\n" + "=" * 70)
    print("检查引擎 _backtest_dates")
    print("=" * 70)
    
    if hasattr(engine, '_backtest_dates'):
        backtest_dates = engine._backtest_dates
        print(f"\n引擎 _backtest_dates 样本:")
        sample_dates = ['2025-01-02', '2025-01-23', '2025-04-17']
        for d in sample_dates:
            in_set = d in backtest_dates
            print(f"  {d} in _backtest_dates: {in_set}")
        
        print(f"\n引擎 _backtest_dates 日期数量: {len(backtest_dates)}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
