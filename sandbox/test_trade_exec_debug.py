"""
测试交易执行流程
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
                print(f"[Signal] {current_date}: 金叉买入信号")
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                print(f"[Signal] {current_date}: 死叉卖出信号")
        
        return signals


print("=" * 70)
print("交易执行流程调试")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 手动运行回测来调试
    print("\n[2] 手动运行回测调试...")
    
    # 设置回测参数
    start_date = '2025-01-01'
    end_date = '2025-02-28'  # 只跑2个月，更快
    
    # 获取交易日历
    trading_dates = data_query.get_trading_dates(start_date, end_date)
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  交易日数量: {len(trading_dates)}")
    
    # 运行回测
    events = list(engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy
    ))
    
    print(f"\n[3] 回测完成，事件数量: {len(events)}")
    
    # 检查每一天的信号和持仓
    print("\n" + "=" * 70)
    print("每日信号和持仓状态")
    print("=" * 70)
    
    for event in events:
        date = event.get('date', '')
        signals = event.get('signals', {})
        portfolio = event.get('portfolio', {})
        cash = event.get('cash', 0)
        trades = event.get('trades', [])
        
        if signals or trades:
            print(f"\n{date}:")
            if signals:
                print(f"  信号: {signals}")
            if portfolio:
                print(f"  持仓: {portfolio}")
            print(f"  现金: {cash:.2f}")
            if trades:
                for trade in trades:
                    print(f"  交易: {trade.action} {trade.code} {trade.shares}股 @ {trade.price:.2f}")
    
    # 最终结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    if events:
        final_event = events[-1]
        metrics = final_event.get('metrics', {})
        
        print(f"\n  初始资金: 100,000")
        print(f"  最终资金: {metrics.get('final_value', 100000):.2f}")
        print(f"  策略收益: {metrics.get('total_return', 0):.2%}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
        
        # 统计所有交易
        all_trades = []
        for event in events:
            all_trades.extend(event.get('trades', []))
        
        print(f"\n  所有交易记录 ({len(all_trades)}笔):")
        for trade in all_trades:
            print(f"    {trade.date}: {trade.action} {trade.code} {trade.shares}股 @ {trade.price:.2f}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
