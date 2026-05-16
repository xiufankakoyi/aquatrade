"""
调试信号生成过程
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.vectorized_base import VectorizedStrategyBase


class DebugMACrossStrategy(VectorizedStrategyBase):
    """调试版MA金叉死叉策略"""
    
    strategy_id = "debug_ma_cross"
    strategy_name = "调试MA金叉死叉策略"
    
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
        
        print(f"\n[Strategy Debug]")
        print(f"  交易日期数量: {T}")
        print(f"  股票数量: {N}")
        print(f"  目标股票: {self.target_stock}")
        print(f"  股票池前10: {stock_codes[:10]}")
        
        if self.target_stock not in stock_codes:
            print(f"  ⚠️ 目标股票不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        print(f"  目标股票索引: {n_idx}")
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        print(f"  MA5: {self.ma5 is not None}")
        print(f"  MA10: {self.ma10 is not None}")
        
        if self.ma5 is None or self.ma10 is None:
            print(f"  ⚠️ MA数据未加载")
            return signals
        
        print(f"  MA5形状: {self.ma5.shape}")
        print(f"  MA10形状: {self.ma10.shape}")
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        print(f"\n  日期T的MA数据（前10天）:")
        for t in range(min(10, T)):
            date = trading_dates[t]
            ma5_val = ma5_stock[t]
            ma10_val = ma10_stock[t]
            print(f"    {date}: MA5={ma5_val:.4f}, MA10={ma10_val:.4f}")
        
        # 计算金叉死叉 - 使用昨日数据判断，今日执行
        signal_count = 0
        for t in range(1, T):
            if np.isnan(ma5_stock[t-1]) or np.isnan(ma10_stock[t-1]):
                continue
            
            if t >= 2 and not np.isnan(ma5_stock[t-2]) and not np.isnan(ma10_stock[t-2]):
                prev_ma5 = ma5_stock[t-1]
                prev_ma10 = ma10_stock[t-1]
                prev2_ma5 = ma5_stock[t-2]
                prev2_ma10 = ma10_stock[t-2]
                
                date = trading_dates[t]
                
                # 金叉
                if prev2_ma5 < prev2_ma10 and prev_ma5 > prev_ma10:
                    signals[t, n_idx] = 1
                    signal_count += 1
                    print(f"  ✓ 金叉信号 @ {date}: 前日MA5={prev2_ma5:.4f}, 前日MA10={prev2_ma10:.4f}, "
                          f"昨日MA5={prev_ma5:.4f}, 昨日MA10={prev_ma10:.4f}")
                    
                # 死叉
                elif prev2_ma5 > prev2_ma10 and prev_ma5 < prev_ma10:
                    signals[t, n_idx] = -1
                    signal_count += 1
                    print(f"  ✓ 死叉信号 @ {date}: 前日MA5={prev2_ma5:.4f}, 前日MA10={prev2_ma10:.4f}, "
                          f"昨日MA5={prev_ma5:.4f}, 昨日MA10={prev_ma10:.4f}")
        
        print(f"\n  信号总数: {signal_count}")
        
        return signals


print("=" * 70)
print("调试信号生成")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = DebugMACrossStrategy(stock_code='000001')
    
    config = BacktestConfig(
        initial_capital=100000,
        position_ratio=0.95,
        commission_rate=0.0003,
        min_commission=5.0
    )
    
    engine = UnifiedBacktestEngine(data_query, config=config)
    print(f"  ✓ 初始化完成")

    # 运行回测
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    print("=" * 70)
    
    all_events = []
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy=strategy
    ):
        all_events.append(event)
    
    print(f"\n[3] 回测完成")
    
    # 提取交易记录
    trades = [e.get('data', {}) for e in all_events if e.get('type') == 'new_trade_engine']
    
    print(f"\n[4] 交易记录 ({len(trades)}笔):")
    for i, trade in enumerate(trades):
        print(f"  {i+1}. {trade.get('date')} {trade.get('action')} {trade.get('code')} "
              f"{trade.get('shares')}股 @ {trade.get('price'):.2f}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
