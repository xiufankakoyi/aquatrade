"""
完整回测测试 - 验证交易是否正常执行
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


class MACrossStrategyFinal(VectorizedStrategyBase):
    """MA金叉死叉策略 - 最终版"""
    
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
            
            # 金叉: MA5上穿MA10
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉: MA5下穿MA10
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("MA金叉死叉策略 - 完整回测")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyFinal(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print(f"   策略: MA5/MA10金叉死叉")
    print(f"   标的: 000001 (平安银行)")
    print("=" * 70)
    
    all_events = []
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        all_events.append(event)
    
    print(f"\n[3] 回测完成，事件数量: {len(all_events)}")
    
    # 提取交易记录
    trades = []
    equity_curve = []
    
    for event in all_events:
        if event.get('type') == 'trade':
            trades.append(event.get('data', {}))
        elif event.get('type') == 'daily_equity_engine':
            equity_curve.append(event.get('data', {}))
    
    # 显示交易记录
    print("\n" + "=" * 70)
    print(f"交易记录 ({len(trades)}笔)")
    print("=" * 70)
    
    if trades:
        for i, trade in enumerate(trades[:20]):  # 只显示前20笔
            date = trade.get('date', '')
            action = trade.get('action', '')
            code = trade.get('code', '')
            shares = trade.get('shares', 0)
            price = trade.get('price', 0)
            amount = trade.get('amount', 0)
            print(f"  {i+1}. {date} {action:4} {code} {shares:5}股 @ {price:7.2f} = {amount:10.2f}")
        
        if len(trades) > 20:
            print(f"  ... 还有 {len(trades) - 20} 笔交易")
    else:
        print("  无交易记录")
    
    # 显示最终结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    # 从最后一个权益曲线事件获取最终资金
    if equity_curve:
        final_equity = equity_curve[-1].get('equity', 100000)
        initial_equity = 100000
        total_return = (final_equity - initial_equity) / initial_equity
        
        print(f"\n  初始资金: {initial_equity:,.2f}")
        print(f"  最终资金: {final_equity:,.2f}")
        print(f"  策略收益: {total_return:.2%}")
        print(f"  交易次数: {len(trades)}")
        
        # 计算基准收益 (000001的涨跌幅)
        if equity_curve:
            first_date = equity_curve[0].get('date', '')
            last_date = equity_curve[-1].get('date', '')
            
            # 获取000001的首尾价格
            try:
                first_price_data = data_query.get_stock_data('000001', first_date, first_date)
                last_price_data = data_query.get_stock_data('000001', last_date, last_date)
                
                if not first_price_data.empty and not last_price_data.empty:
                    first_close = first_price_data['close'].iloc[0]
                    last_close = last_price_data['close'].iloc[0]
                    benchmark_return = (last_close - first_close) / first_close
                    
                    print(f"  基准收益: {benchmark_return:.2%}")
                    print(f"  Alpha: {total_return - benchmark_return:.2%}")
            except Exception as e:
                print(f"  基准收益计算失败: {e}")
    
    print("\n" + "=" * 70)
    print("回测完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
