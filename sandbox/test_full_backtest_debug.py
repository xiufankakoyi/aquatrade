"""
完整回测调试
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
print("完整回测调试")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 手动预加载数据
    print("\n[2] 预加载数据...")
    engine._preload_data(pd.Timestamp('2025-01-01'), pd.Timestamp('2025-01-31'))
    preloaded = getattr(engine.data_query, '_preloaded_data', None)
    print(f"  ✓ 预加载完成: {len(preloaded) if preloaded else 0} 个日期")
    
    # 获取交易日
    print("\n[3] 获取交易日...")
    time_series = [pd.Timestamp(d) for d in data_query.get_trading_dates('2025-01-01', '2025-01-31')]
    print(f"  ✓ 交易日数量: {len(time_series)}")
    
    # 手动调用 _generate_vectorized_signals
    print("\n[4] 生成向量化信号...")
    day1_signals = engine._generate_vectorized_signals(
        strategy=strategy,
        preloaded_data=preloaded,
        time_series=time_series,
        current_time=time_series[0]
    )
    print(f"  ✓ 第1天信号: {len(day1_signals)} 个")
    
    # 检查引擎状态
    print("\n[5] 检查引擎状态...")
    print(f"   _vectorized_mode: {getattr(engine, '_vectorized_mode', False)}")
    print(f"   _signal_matrix 形状: {engine._signal_matrix.shape if hasattr(engine, '_signal_matrix') and engine._signal_matrix is not None else 'None'}")
    print(f"   _stock_codes_list 长度: {len(engine._stock_codes_list) if hasattr(engine, '_stock_codes_list') else 'None'}")
    print(f"   _date_to_idx: {list(engine._date_to_idx.keys())[:5] if hasattr(engine, '_date_to_idx') else 'None'}...")
    print(f"   _backtest_dates: {list(engine._backtest_dates)[:5] if hasattr(engine, '_backtest_dates') else 'None'}...")
    
    # 检查信号矩阵
    if engine._signal_matrix is not None:
        print(f"\n[6] 检查信号矩阵...")
        print(f"   信号矩阵非零元素数量: {np.sum(engine._signal_matrix != 0)}")
        
        # 找到所有信号
        non_zero_indices = np.argwhere(engine._signal_matrix != 0)
        print(f"   信号位置:")
        for t_idx, n_idx in non_zero_indices[:10]:
            date = list(engine._date_to_idx.keys())[list(engine._date_to_idx.values()).index(t_idx)]
            code = engine._stock_codes_list[n_idx]
            signal = engine._signal_matrix[t_idx, n_idx]
            print(f"     {date} {code}: {'买入' if signal == 1 else '卖出'}")
    
    # 模拟每天的信号获取
    print(f"\n[7] 模拟每天信号获取...")
    for i, ts in enumerate(time_series[:5]):
        signals = engine._get_vectorized_signals_for_day(ts)
        if signals:
            print(f"   {ts.strftime('%Y-%m-%d')}: {signals}")
    
    # 检查 2025-01-23 的信号
    print(f"\n[8] 检查 2025-01-23 的信号...")
    test_time = pd.Timestamp('2025-01-23')
    signals = engine._get_vectorized_signals_for_day(test_time)
    print(f"   信号: {signals}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
