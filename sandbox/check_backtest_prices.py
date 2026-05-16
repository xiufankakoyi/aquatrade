"""
检查回测中实际使用的价格数据
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
    """调试策略 - 只打印价格数据"""
    
    def __init__(self):
        self.name = "DebugStrategy"
        self.description = "调试策略 - 打印价格数据"
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None
    ) -> np.ndarray:
        """打印价格数据"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        # 打印2025-01-21和2025-01-24的价格数据
        for t, date in enumerate(trading_dates):
            if date in ['2025-01-21', '2025-01-24']:
                n = self.target_idx
                open_price = price_matrix[t, n, 0]
                high_price = price_matrix[t, n, 1]
                low_price = price_matrix[t, n, 2]
                close_price = price_matrix[t, n, 3]
                print(f"\n【{date} 价格矩阵数据】")
                print(f"  开盘价(open): {open_price}")
                print(f"  最高价(high): {high_price}")
                print(f"  最低价(low): {low_price}")
                print(f"  收盘价(close): {close_price}")
        
        return signals


print("=" * 70)
print("检查回测中实际使用的价格数据")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = DebugStrategy()
    
    print("\n[2] 运行回测（仅查看价格数据）...")
    
    for event in engine.run_backtest('2025-01-21', '2025-01-24', strategy):
        pass  # 不处理事件，只让策略打印价格
    
    print("\n" + "=" * 70)
    print("对比聚宽的价格:")
    print("=" * 70)
    print("2025-01-21: 开盘价11.46 (聚宽买入价)")
    print("2025-01-24: 开盘价11.32 (聚宽开盘价)，但卖出成交价11.31")
    print("\n差异分析:")
    print("- 如果AquaTrade的开盘价与聚宽不同，说明数据源有差异")
    print("- 聚宽卖出价11.31可能是滑点或市场冲击模型导致的")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
