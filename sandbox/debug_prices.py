"""
检查价格矩阵数据
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


class DebugStrategy3:
    """调试策略 - 检查价格数据"""
    
    def __init__(self):
        self.name = "Debug3"
        self.description = "检查价格数据"
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None,
        price_matrix_adj: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """检查价格数据"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            print("未找到000001")
            return signals
        
        n = self.target_idx
        
        print(f"\n【股票代码列表】前10个: {stock_codes[:10]}")
        print(f"【000001索引】: {n}")
        
        # 检查价格数据
        print(f"\n【价格矩阵形状】: {price_matrix.shape}")
        print(f"【前复权价格矩阵】: {'有' if price_matrix_adj is not None else '无'}")
        
        # 打印关键日期的价格
        print(f"\n【关键日期价格数据】")
        for t in range(len(trading_dates)):
            date = trading_dates[t]
            if date in ['2025-01-20', '2025-01-21', '2025-02-05', '2025-02-06', '2025-02-07', '2025-02-10']:
                open_p = price_matrix[t, n, 0]
                close_p = price_matrix[t, n, 3]
                
                if price_matrix_adj is not None:
                    open_adj = price_matrix_adj[t, n, 0]
                    close_adj = price_matrix_adj[t, n, 3]
                    print(f"  索引{t}: {date} open={open_p:.2f} close={close_p:.2f} | open_adj={open_adj:.2f} close_adj={close_adj:.2f}")
                else:
                    print(f"  索引{t}: {date} open={open_p:.2f} close={close_p:.2f}")
        
        # 检查NaN数量
        close_prices = price_matrix[:, n, 3]
        nan_count = np.sum(np.isnan(close_prices))
        print(f"\n【收盘价NaN数量】: {nan_count}/{T}")
        
        # 打印前20天的收盘价
        print(f"\n【前20天收盘价】")
        for t in range(min(20, T)):
            date = trading_dates[t]
            close_p = price_matrix[t, n, 3]
            print(f"  索引{t}: {date} close={close_p}")
        
        return signals


print("=" * 70)
print("检查价格矩阵数据")
print("=" * 70)

try:
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = DebugStrategy3()
    
    for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
        pass

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
