"""
调试交易执行
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
        print(f"✓ 目标股票 {self.target_stock} 索引: {n_idx}")
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            print(f"⚠️ MA数据为空")
            return signals
        
        print(f"✓ MA5形状: {self.ma5.shape}, MA10形状: {self.ma10.shape}")
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        # 计算金叉死叉
        signal_count = 0
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                print(f"📈 买入信号: {current_date} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                print(f"📉 卖出信号: {current_date} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                signal_count += 1
        
        print(f"✓ 总共生成 {signal_count} 个信号")
        
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

    # 运行回测
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    print("=" * 70)
    
    results_list = []
    trades_log = []
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy=strategy
    ):
        results_list.append(event)
        
        if event.get('type') == 'trade':
            trades_log.append(event)
            trade = event.get('trade', {})
            print(f">>> 交易执行: {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} @ {trade.get('price', 0):.2f}")
    
    # 检查因子矩阵
    print("\n" + "=" * 70)
    print("检查因子矩阵")
    print("=" * 70)
    
    if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
        fm = engine._factor_matrix
        print(f"\n因子矩阵形状: {fm.values.shape}")
        print(f"因子矩阵日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
        
        # 检查 000001 的数据
        if '000001' in fm.codes_str:
            stock_idx = fm.codes_str.index('000001')
            print(f"\n000001 在因子矩阵中的索引: {stock_idx}")
            
            # 检查 open 和 close
            open_idx = fm.factor_names.index('open') if 'open' in fm.factor_names else -1
            close_idx = fm.factor_names.index('close') if 'close' in fm.factor_names else -1
            
            if open_idx >= 0 and close_idx >= 0:
                print(f"\nopen 因子索引: {open_idx}, close 因子索引: {close_idx}")
                
                # 检查 2025-01-23 的数据
                date_str = '2025-01-23'
                date_idx = fm.date_to_idx.get(date_str, -1)
                print(f"\n{date_str} 在因子矩阵中的索引: {date_idx}")
                
                if date_idx >= 0:
                    open_val = fm.values[date_idx, stock_idx, open_idx]
                    close_val = fm.values[date_idx, stock_idx, close_idx]
                    print(f"{date_str} 000001:")
                    print(f"  open: {open_val}")
                    print(f"  close: {close_val}")
    
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
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
    
    print(f"\n  交易记录 ({len(trades_log)} 笔):")
    if trades_log:
        for trade_event in trades_log:
            trade = trade_event.get('trade', {})
            print(f"    {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} "
                  f"@{trade.get('price', 0):.2f}")
    else:
        print("    无交易")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
