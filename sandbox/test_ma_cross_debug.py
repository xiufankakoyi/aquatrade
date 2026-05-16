"""
MA金叉死叉策略测试 - 调试版
详细检查信号生成和交易执行
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
        self.signal_log = []
        self.signals_generated = None
        
    def generate_signals_vectorized(
        self,
        price_matrix,
        trading_dates: list,
        stock_codes: list,
        data_query,
        preloaded_data=None
    ) -> np.ndarray:
        """
        生成交易信号
        信号: 1=买入, -1=卖出, 0=无操作
        """
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        print(f"\n[策略调试] 生成信号 - T={T}, N={N}")
        print(f"[策略调试] 回测日期范围: {trading_dates[0]} ~ {trading_dates[-1]}")
        print(f"[策略调试] 目标股票: {self.target_stock}")
        
        # 找到目标股票的索引
        if self.target_stock not in stock_codes:
            print(f"[策略调试] 错误: 股票 {self.target_stock} 不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        print(f"[策略调试] 目标股票索引: {n_idx}")
        
        # 使用 prepare_data 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 检查MA数据
        print(f"\n[策略调试] MA数据检查:")
        print(f"  ma5 shape: {self.ma5.shape if self.ma5 is not None else 'None'}")
        print(f"  ma10 shape: {self.ma10.shape if self.ma10 is not None else 'None'}")
        
        if self.ma5 is None or self.ma10 is None:
            print(f"[策略调试] 错误: MA数据为空")
            return signals
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        print(f"  MA5 前5个值: {ma5_stock[:5]}")
        print(f"  MA10 前5个值: {ma10_stock[:5]}")
        print(f"  MA5 NaN数量: {np.sum(np.isnan(ma5_stock))}")
        print(f"  MA10 NaN数量: {np.sum(np.isnan(ma10_stock))}")
        
        # 计算金叉死叉
        cross_count = 0
        for t in range(1, T):
            # 跳过NaN值
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            # 金叉: MA5上穿MA10 (昨天MA5<MA10, 今天MA5>MA10)
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                cross_count += 1
                self.signal_log.append({
                    'date': current_date,
                    'type': '金叉',
                    'ma5': ma5_stock[t],
                    'ma10': ma10_stock[t],
                    't_idx': t
                })
                print(f"  [信号{t}] {current_date} 金叉 MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                
            # 死叉: MA5下穿MA10 (昨天MA5>MA10, 今天MA5<MA10)
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                cross_count += 1
                self.signal_log.append({
                    'date': current_date,
                    'type': '死叉',
                    'ma5': ma5_stock[t],
                    'ma10': ma10_stock[t],
                    't_idx': t
                })
                print(f"  [信号{t}] {current_date} 死叉 MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
        
        print(f"\n[策略调试] 总共生成 {cross_count} 个信号")
        print(f"[策略调试] 买入信号数量: {np.sum(signals == 1)}")
        print(f"[策略调试] 卖出信号数量: {np.sum(signals == -1)}")
        
        self.signals_generated = signals.copy()
        return signals


print("=" * 70)
print("MA金叉死叉策略测试 - 调试版")
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
    print("=" * 70)
    
    results_list = []
    trades_log = []
    day_count = 0
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        day_count += 1
        results_list.append(event)
        
        # 记录交易
        if event.get('type') == 'trade':
            trades_log.append(event)
            trade = event.get('trade', {})
            print(f"\n>>> 交易执行: {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} "
                  f"价格:{trade.get('price', 0):.2f} 数量:{trade.get('quantity', 0)}")
        
        # 只显示前5天的详细日志
        if day_count <= 5:
            print(f"\n[Day {day_count}] 事件类型: {event.get('type')}")
            if 'date' in event:
                print(f"  日期: {event.get('date')}")
            if 'signals' in event:
                signals = event.get('signals', {})
                if '000001' in signals:
                    print(f"  000001信号: {signals['000001']}")
    
    print(f"\n[调试] 共处理 {day_count} 天")
    
    # 显示信号日志
    print("\n" + "=" * 70)
    print("信号生成日志")
    print("=" * 70)
    if strategy.signal_log:
        print(f"\n  共发现 {len(strategy.signal_log)} 个信号:")
        for sig in strategy.signal_log:
            print(f"    {sig['date']} {sig['type']} MA5={sig['ma5']:.2f} MA10={sig['ma10']:.2f} t_idx={sig.get('t_idx', 'N/A')}")
    else:
        print("\n  没有发现任何信号")
    
    # 检查结果
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
    
    # 显示交易记录
    print(f"\n  交易记录 ({len(trades_log)} 笔):")
    if trades_log:
        for trade_event in trades_log:
            trade = trade_event.get('trade', {})
            print(f"    {trade.get('date')} {trade.get('action'):4} {trade.get('stock_code')} "
                  f"@{trade.get('price', 0):.2f} x {trade.get('quantity', 0)}")
    else:
        print("    无交易记录")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
