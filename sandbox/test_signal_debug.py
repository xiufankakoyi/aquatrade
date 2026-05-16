"""
调试信号获取
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
            print(f"⚠️ 目标股票 {self.target_stock} 不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        print(f"✓ 目标股票 {self.target_stock} 索引: {n_idx}")
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            print(f"⚠️ MA数据为空")
            return signals
        
        print(f"✓ MA5形状: {self.ma5.shape}, MA10形状: {self.ma10.shape}")
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        # 计算金叉死叉
        signal_count = 0
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                print(f"📈 买入信号: {current_date} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                print(f"📉 卖出信号: {current_date} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
        
        print(f"✓ 总共生成 {signal_count} 个信号")
        
        return signals


print("=" * 70)
print("调试信号获取")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 手动运行回测的第1天来调试
    print("\n[2] 手动测试信号获取...")
    
    # 获取交易日
    trading_dates = data_query.get_trading_dates('2025-01-01', '2025-01-31')
    print(f"   交易日数量: {len(trading_dates)}")
    print(f"   交易日: {trading_dates[:5]}...")
    
    # 手动调用 _generate_vectorized_signals
    from datetime import datetime
    current_time = pd.Timestamp('2025-01-02')
    
    print("\n[3] 调用 _generate_vectorized_signals...")
    signals = engine._generate_vectorized_signals(
        current_time=current_time,
        preloaded_data=getattr(engine.data_query, '_preloaded_data', None),
        strategy=strategy,
        backtest_dates=trading_dates
    )
    
    print(f"\n[4] 检查引擎状态...")
    print(f"   _vectorized_mode: {getattr(engine, '_vectorized_mode', False)}")
    print(f"   _signal_matrix 形状: {engine._signal_matrix.shape if hasattr(engine, '_signal_matrix') and engine._signal_matrix is not None else 'None'}")
    print(f"   _stock_codes_list 长度: {len(engine._stock_codes_list) if hasattr(engine, '_stock_codes_list') else 'None'}")
    print(f"   _date_to_idx 长度: {len(engine._date_to_idx) if hasattr(engine, '_date_to_idx') else 'None'}")
    print(f"   _backtest_dates 长度: {len(engine._backtest_dates) if hasattr(engine, '_backtest_dates') else 'None'}")
    
    # 检查特定日期的信号
    print(f"\n[5] 检查 2025-01-23 的信号...")
    test_date = '2025-01-23'
    t_idx = engine._date_to_idx.get(test_date, -1)
    print(f"   {test_date} 索引: {t_idx}")
    
    if t_idx >= 0 and engine._signal_matrix is not None:
        day_signals = engine._signal_matrix[t_idx, :]
        print(f"   当天信号数量: {np.sum(day_signals != 0)}")
        
        # 检查 000001 的信号
        if '000001' in engine._stock_codes_list:
            stock_idx = engine._stock_codes_list.index('000001')
            signal_val = day_signals[stock_idx]
            print(f"   000001 信号值: {signal_val}")
    
    # 测试 _get_vectorized_signals_for_day
    print(f"\n[6] 测试 _get_vectorized_signals_for_day...")
    test_time = pd.Timestamp('2025-01-23')
    day_signals = engine._get_vectorized_signals_for_day(test_time)
    print(f"   返回信号数量: {len(day_signals)}")
    print(f"   信号: {day_signals}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
