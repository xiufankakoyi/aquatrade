"""
MA金叉死叉策略测试 - 最终版
验证完整回测流程
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


class MACrossStrategyFinal(VectorizedStrategyBase):
    """简单均线金叉死叉策略 - 最终版"""
    
    strategy_id = "ma_cross_final"
    strategy_name = "MA金叉死叉策略-最终版"
    
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
            
            current_date = trading_dates[t]
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("MA金叉死叉策略测试 - 最终版")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyFinal(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行完整回测
    print("\n[2] 运行完整回测...")
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print("=" * 70)
    
    results_list = []
    trades_log = []
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        results_list.append(event)
        
        if event.get('type') == 'trade':
            trades_log.append(event)
            trade = event.get('trade', {})
            print(f">>> 交易执行: {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} @ {trade.get('price', 0):.2f}")
    
    # 检查因子矩阵
    print("\n" + "=" * 70)
    print("检查因子矩阵状态")
    print("=" * 70)
    
    if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
        fm = engine._factor_matrix
        print(f"\n因子矩阵形状: {fm.values.shape}")
        print(f"因子矩阵日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
        print(f"因子矩阵日期数量: {len(fm.dates)}")
    else:
        print("因子矩阵未初始化!")
    
    # 显示结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    if results_list:
        final_result = results_list[-1]
        metrics = final_result.get('metrics', {})
        
        print(f"\n  初始资金: 100,000")
        print(f"  最终资金: {metrics.get('final_value', 100000):.2f}")
        print(f"  策略收益: {metrics.get('total_return', 0):.2%}")
        print(f"  基准收益: {metrics.get('benchmark_return', 0):.2%}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2%}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    
    print(f"\n  交易记录 ({len(trades_log)} 笔):")
    if trades_log:
        for trade_event in trades_log:
            trade = trade_event.get('trade', {})
            print(f"    {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} "
                  f"@{trade.get('price', 0):.2f}")
    else:
        print("    无交易")
    
    print("\n" + "=" * 70)
    print("与聚宽对比:")
    print("  聚宽策略收益: 5.24%")
    print("  聚宽基准收益: 17.66%")
    print("  聚宽最大回撤: 10.10%")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
