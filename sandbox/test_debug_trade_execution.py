"""
调试交易执行 - 检查为什么买入信号没有触发交易
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
    """MA金叉死叉策略 - 调试版"""
    
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
        
        # 计算金叉死叉
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            # 金叉: MA5上穿MA10
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉: MA5下穿MA10
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("调试交易执行")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测到第一个买入信号日
    print("\n[2] 运行回测到 2025-04-17 (第一个买入信号日)...")
    print("=" * 70)
    
    all_events = []
    target_date = '2025-04-17'
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-04-30',  # 跑到4月底
        strategy=strategy
    ):
        all_events.append(event)
        
        # 检查是否到达目标日期
        if event.get('type') == 'daily_equity_engine':
            if event.get('data', {}).get('date') == target_date:
                print(f"\n到达目标日期 {target_date}")
                break
    
    print(f"\n[3] 检查引擎状态...")
    
    # 检查信号矩阵
    if hasattr(engine, '_signal_matrix') and engine._signal_matrix is not None:
        print(f"\n   信号矩阵形状: {engine._signal_matrix.shape}")
        
        # 检查 2025-04-17 的信号
        t_idx = engine._date_to_idx.get('2025-04-17', -1)
        if t_idx >= 0:
            day_signals = engine._signal_matrix[t_idx, :]
            non_zero = np.where(day_signals != 0)[0]
            print(f"   2025-04-17 (t={t_idx}):")
            for idx in non_zero:
                stock_code = engine._stock_codes_list[idx]
                signal_value = day_signals[idx]
                print(f"      {stock_code}: 信号={signal_value}")
    
    # 检查 _get_vectorized_signals_for_day
    print(f"\n   手动调用 _get_vectorized_signals_for_day('2025-04-17'):")
    ts = pd.Timestamp('2025-04-17')
    signals = engine._get_vectorized_signals_for_day(ts)
    print(f"      返回信号: {signals}")
    
    # 检查 _load_day_data
    print(f"\n   手动调用 _load_day_data('2025-04-17'):")
    stock_pool, use_pl, data_dict = engine._load_day_data(ts)
    print(f"      stock_pool类型: {type(stock_pool)}")
    print(f"      use_pl: {use_pl}")
    print(f"      data_dict中的股票: {list(data_dict.keys())[:5]}...")
    
    if '000001' in data_dict:
        print(f"      000001数据:")
        for k, v in data_dict['000001'].items():
            print(f"        {k}: {v}")
    
    # 显示事件
    print(f"\n[4] 事件记录 (前20个):")
    for i, event in enumerate(all_events[:20]):
        event_type = event.get('type', '')
        if event_type == 'trade':
            data = event.get('data', {})
            print(f"   {i+1}. TRADE: {data.get('date')} {data.get('action')} {data.get('code')} {data.get('shares')}股")
        elif event_type == 'daily_equity_engine':
            data = event.get('data', {})
            print(f"   {i+1}. EQUITY: {data.get('date')} equity={data.get('equity'):.2f} positions={data.get('positions')}")
        elif event_type == 'progress':
            print(f"   {i+1}. PROGRESS: {event.get('data', {}).get('progress')}%")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
