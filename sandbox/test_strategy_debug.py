"""
调试策略信号生成
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
        print(f"\n[Strategy] generate_signals_vectorized 被调用")
        print(f"   trading_dates: {len(trading_dates)} 天")
        print(f"   stock_codes: {len(stock_codes)} 只")
        print(f"   target_stock: {self.target_stock}")
        
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_stock not in stock_codes:
            print(f"   ⚠️ 目标股票 {self.target_stock} 不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        print(f"   ✓ 目标股票索引: {n_idx}")
        
        # 准备数据
        print(f"   [Strategy] 调用 prepare_data...")
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        print(f"   [Strategy] prepare_data 完成")
        print(f"   ma5: {self.ma5 is not None}")
        print(f"   ma10: {self.ma10 is not None}")
        
        if self.ma5 is None or self.ma10 is None:
            print(f"   ⚠️ MA数据为空")
            return signals
        
        print(f"   ma5形状: {self.ma5.shape}")
        print(f"   ma10形状: {self.ma10.shape}")
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
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
                print(f"   📈 买入信号: {trading_dates[t]} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                print(f"   📉 卖出信号: {trading_dates[t]} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
        
        print(f"   ✓ 总共生成 {signal_count} 个信号")
        
        return signals


print("=" * 70)
print("调试策略信号生成")
print("=" * 70)

# 初始化
data_query = OptimizedStockDataQuery()
strategy = MACrossStrategyDebug(stock_code='000001')
engine = UnifiedBacktestEngine(data_query)

# 预加载数据
print("\n[1] 预加载数据...")
engine._preload_data(pd.Timestamp('2025-01-01'), pd.Timestamp('2025-01-31'))

# 检查因子矩阵
print("\n[2] 检查因子矩阵...")
fm = engine._factor_matrix
if fm:
    print(f"   因子矩阵形状: {fm.values.shape}")
    print(f"   日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    print(f"   股票数量: {len(fm.codes_str)}")
    print(f"   因子名称: {fm.factor_names}")
    
    # 检查 000001 是否在股票列表中
    if '000001' in fm.codes_str:
        print(f"   ✓ 000001 在股票列表中，索引: {fm.codes_str.index('000001')}")
    else:
        print(f"   ✗ 000001 不在股票列表中")
        print(f"   前10个股票: {fm.codes_str[:10]}")
    
    # 检查 ma5 和 ma10 因子是否存在
    if 'ma5' in fm.factor_names:
        print(f"   ✓ ma5 因子存在，索引: {fm.factor_names.index('ma5')}")
    else:
        print(f"   ✗ ma5 因子不存在")
    
    if 'ma10' in fm.factor_names:
        print(f"   ✓ ma10 因子存在，索引: {fm.factor_names.index('ma10')}")
    else:
        print(f"   ✗ ma10 因子不存在")

# 手动调用策略生成信号
print("\n[3] 手动调用策略生成信号...")
signals = strategy.generate_signals_vectorized(
    price_matrix=None,
    trading_dates=fm.dates,
    stock_codes=fm.codes_str,
    data_query=data_query,
    preloaded_data=None
)

print(f"\n[4] 信号结果:")
print(f"   信号矩阵形状: {signals.shape}")
print(f"   非零信号数: {np.sum(signals != 0)}")

print("\n" + "=" * 70)
print("调试完成!")
print("=" * 70)
