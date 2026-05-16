"""
检查回测日期范围内的所有信号
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
        
        if self.target_stock not in stock_codes:
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            return signals
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        # 计算金叉死叉
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("检查回测日期范围内的所有信号")
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
    end_date = '2026-01-01'
    
    # 只运行第一天来构建信号矩阵
    for event in engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy
    ):
        if event.get('type') == 'progress':
            break  # 只跑一天就停止
    
    print(f"\n[3] 检查信号矩阵...")
    
    # 获取回测日期
    backtest_dates = sorted(list(engine._backtest_dates))
    print(f"   回测日期数量: {len(backtest_dates)}")
    print(f"   范围: {backtest_dates[0]} ~ {backtest_dates[-1]}")
    
    # 检查每个回测日期的信号
    print(f"\n   回测日期范围内的信号:")
    buy_signals = []
    sell_signals = []
    
    for date_str in backtest_dates:
        t_idx = engine._date_to_idx.get(date_str, -1)
        if t_idx >= 0 and t_idx < engine._signal_matrix.shape[0]:
            day_signals = engine._signal_matrix[t_idx, :]
            non_zero = np.where(day_signals != 0)[0]
            
            for idx in non_zero:
                signal_value = day_signals[idx]
                stock_code = engine._stock_codes_list[idx]
                if signal_value == 1:
                    buy_signals.append((date_str, stock_code))
                    print(f"      {date_str}: 买入信号 ({stock_code})")
                elif signal_value == -1:
                    sell_signals.append((date_str, stock_code))
                    print(f"      {date_str}: 卖出信号 ({stock_code})")
    
    print(f"\n   统计:")
    print(f"      买入信号: {len(buy_signals)} 个")
    print(f"      卖出信号: {len(sell_signals)} 个")
    
    if buy_signals:
        print(f"\n   第一个买入信号: {buy_signals[0][0]}")
    if sell_signals:
        print(f"   第一个卖出信号: {sell_signals[0][0]}")
    
    print("\n" + "=" * 70)
    print("检查完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
