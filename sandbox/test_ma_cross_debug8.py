"""
MA金叉死叉策略测试 - 调试版8
检查因子矩阵中的实际数据
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
print("MA金叉死叉策略测试 - 调试版8")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测（只运行一天来初始化）
    print("\n[2] 运行回测初始化...")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-05")
    print("=" * 70)
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-05',
        strategy=strategy
    ):
        pass  # 只运行初始化
    
    # 检查因子矩阵
    print("\n" + "=" * 70)
    print("检查因子矩阵中的数据")
    print("=" * 70)
    
    if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
        fm = engine._factor_matrix
        
        print(f"\n因子矩阵形状: {fm.values.shape}")
        print(f"因子名称: {fm.factor_names}")
        
        # 找到000001的索引
        if '000001' in fm.codes_str:
            stock_idx = fm.codes_str.index('000001')
            print(f"\n000001 在因子矩阵中的索引: {stock_idx}")
            
            # 找到2025-01-23的日期索引
            date_str = '2025-01-23'
            date_idx = fm.date_to_idx.get(date_str, -1)
            print(f"{date_str} 在因子矩阵中的索引: {date_idx}")
            
            if date_idx >= 0:
                # 获取该日期000001的数据
                factor_slice = fm.values[date_idx, stock_idx, :]
                print(f"\n{date_str} 000001 的因子数据:")
                for i, name in enumerate(fm.factor_names):
                    print(f"  {name}: {factor_slice[i]}")
        else:
            print(f"000001 不在因子矩阵中!")
    else:
        print("因子矩阵未初始化!")
    
    # 检查预加载数据
    print("\n" + "=" * 70)
    print("检查预加载数据")
    print("=" * 70)
    
    # 重新初始化来获取预加载数据
    from data_svc.unified_data_manager import UnifiedDataManager
    data_manager = UnifiedDataManager()
    
    start_date = '2025-01-01'
    end_date = '2026-01-01'
    
    preloaded_data = data_manager.preload_to_memory(
        start_date=start_date,
        end_date=end_date,
        stock_codes=['000001']
    )
    
    if 'stock_daily' in preloaded_data:
        df = preloaded_data['stock_daily']
        print(f"\nstock_daily 数据:")
        print(f"  形状: {df.shape}")
        print(f"  列: {df.columns}")
        
        # 过滤000001的数据
        df_000001 = df.filter(pl.col('stock_code') == '000001')
        print(f"\n000001 的数据行数: {len(df_000001)}")
        
        if len(df_000001) > 0:
            print(f"\n000001 前5行数据:")
            print(df_000001.head(5).to_pandas())
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
