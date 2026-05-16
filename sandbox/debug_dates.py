"""
检查因子矩阵的日期范围
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


class DebugStrategy:
    """调试策略"""
    
    def __init__(self):
        self.name = "Debug"
        self.description = "调试"
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
        """打印日期范围"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        print(f"\n【因子矩阵日期范围】")
        print(f"  总天数: {T}")
        print(f"  前5天: {trading_dates[:5]}")
        print(f"  后5天: {trading_dates[-5:]}")
        
        # 找到2025-01-21和2025-02-10的索引
        for i, date in enumerate(trading_dates):
            if date in ['2025-01-21', '2025-02-07', '2025-02-10']:
                print(f"  {date} 索引: {i}")
        
        return signals


print("=" * 70)
print("检查因子矩阵日期范围")
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
    
    strategy = DebugStrategy()
    
    for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
        pass

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
