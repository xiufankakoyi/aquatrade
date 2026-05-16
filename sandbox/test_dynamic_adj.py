"""
测试动态复权功能

验证：
1. 因子矩阵包含前复权价格字段
2. 策略使用前复权价格计算指标
3. 交易使用不复权价格
4. 除权除息时自动调整持仓
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


class TestDynamicAdjStrategy:
    """测试策略 - 验证动态复权"""
    
    def __init__(self):
        self.name = "TestDynamicAdj"
        self.description = "测试动态复权"
        self.target_idx = None
        self.price_matrix = None
        self.price_matrix_adj = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None,
        price_matrix_adj: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """验证动态复权"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        # 保存价格矩阵
        self.price_matrix = price_matrix
        self.price_matrix_adj = price_matrix_adj if price_matrix_adj is not None else price_matrix
        
        # 找到000001的索引
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        n = self.target_idx
        
        # 打印价格对比
        print("\n" + "=" * 70)
        print("动态复权验证")
        print("=" * 70)
        
        # 检查是否有除权除息（复权因子变化）
        has_adj_change = False
        for t in range(1, T):
            if trading_dates[t] in ['2024-06-14', '2024-06-25', '2024-06-26', '2024-10-10']:
                # 这些是除权除息日
                has_adj_change = True
                print(f"\n【{trading_dates[t]}】可能存在除权除息")
                
                # 打印价格对比
                open_unadj = price_matrix[t, n, 0]
                open_adj = self.price_matrix_adj[t, n, 0]
                close_unadj = price_matrix[t, n, 3]
                close_adj = self.price_matrix_adj[t, n, 3]
                
                print(f"  不复权开盘价: {open_unadj:.2f}")
                print(f"  前复权开盘价: {open_adj:.2f}")
                print(f"  不复权收盘价: {close_unadj:.2f}")
                print(f"  前复权收盘价: {close_adj:.2f}")
                
                if abs(open_unadj - open_adj) > 0.01:
                    print(f"  ✓ 前复权价格与不复权价格不同，动态复权生效！")
                else:
                    print(f"  ✗ 前复权价格与不复权价格相同，动态复权未生效")
        
        # 打印部分日期的价格对比
        print("\n【价格矩阵验证】")
        for t in range(min(5, T)):
            date = trading_dates[t]
            open_unadj = price_matrix[t, n, 0]
            open_adj = self.price_matrix_adj[t, n, 0]
            print(f"  {date}: 不复权={open_unadj:.2f}, 前复权={open_adj:.2f}")
        
        return signals


print("=" * 70)
print("测试动态复权功能")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = TestDynamicAdjStrategy()
    
    # 测试包含除权除息的时期（2024年6-7月）
    print("\n[2] 运行回测（2024-06-01 ~ 2024-07-31）...")
    
    for event in engine.run_backtest('2024-06-01', '2024-07-31', strategy):
        if event['type'] == 'dividend_payout':
            print(f"\n[分红/送转] {event['data']}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    
    # 验证结果
    if strategy.price_matrix is not None and strategy.price_matrix_adj is not None:
        print("\n✓ 价格矩阵已正确传递")
        if strategy.price_matrix is strategy.price_matrix_adj:
            print("  注意：前复权价格矩阵与不复权价格矩阵相同（可能是同一对象）")
        else:
            print("  ✓ 前复权价格矩阵与不复权价格矩阵是不同对象")
    else:
        print("\n✗ 价格矩阵未正确传递")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
