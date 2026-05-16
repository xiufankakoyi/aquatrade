"""
MA金叉死叉策略 - 无未来函数版本
在日期T开盘前，只能看到T-1及之前的数据
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.vectorized_base import VectorizedStrategyBase


class MACrossStrategyNoLookahead(VectorizedStrategyBase):
    """
    MA金叉死叉策略 - 无未来函数版本
    
    关键设计：
    - 在日期T，只能看到T-1及之前的MA数据
    - 信号基于昨日数据生成，今日开盘执行
    """
    
    strategy_id = "ma_cross_no_lookahead"
    strategy_name = "MA金叉死叉策略-无未来函数"
    
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
        """
        生成交易信号 - 无未来函数版本
        
        逻辑：
        - 在日期T，使用T-1的MA数据判断金叉死叉
        - 如果T-1出现金叉，在T日开盘买入
        - 如果T-1出现死叉，在T日开盘卖出
        """
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
        
        # 计算金叉死叉 - 使用昨日数据判断，今日执行
        for t in range(1, T):
            if np.isnan(ma5_stock[t-1]) or np.isnan(ma10_stock[t-1]):
                continue
            
            if t >= 2 and not np.isnan(ma5_stock[t-2]) and not np.isnan(ma10_stock[t-2]):
                # 昨日MA5和MA10
                prev_ma5 = ma5_stock[t-1]
                prev_ma10 = ma10_stock[t-1]
                # 前日MA5和MA10
                prev2_ma5 = ma5_stock[t-2]
                prev2_ma10 = ma10_stock[t-2]
                
                # 金叉: 前日MA5 < 前日MA10，昨日MA5 > 昨日MA10
                if prev2_ma5 < prev2_ma10 and prev_ma5 > prev_ma10:
                    signals[t, n_idx] = 1  # 今日开盘买入
                    
                # 死叉: 前日MA5 > 前日MA10，昨日MA5 < 昨日MA10
                elif prev2_ma5 > prev2_ma10 and prev_ma5 < prev_ma10:
                    signals[t, n_idx] = -1  # 今日开盘卖出
        
        return signals


print("=" * 70)
print("MA金叉死叉策略 - 无未来函数版本")
print("=" * 70)
print("\n关键设计：")
print("  - 在日期T，只能看到T-1及之前的MA数据")
print("  - 信号基于昨日数据生成，今日开盘执行")
print("  - 避免未来函数（look-ahead bias）")

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyNoLookahead(stock_code='000001')
    
    config = BacktestConfig(
        initial_capital=100000,
        position_ratio=0.95,
        commission_rate=0.0003,
        min_commission=5.0
    )
    
    engine = UnifiedBacktestEngine(data_query, config=config)
    print(f"  ✓ 初始化完成")
    print(f"  初始资金: {config.initial_capital:,.0f}")
    print(f"  仓位比例: {config.position_ratio:.0%}")

    # 运行回测
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    print(f"   策略: MA5/MA10金叉死叉（无未来函数）")
    print(f"   标的: 000001 (平安银行)")
    print("=" * 70)
    
    all_events = []
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy=strategy
    ):
        all_events.append(event)
    
    print(f"\n[3] 回测完成，事件数量: {len(all_events)}")
    
    # 提取交易记录
    trades = []
    equity_curve = []
    
    for event in all_events:
        event_type = event.get('type', '')
        if event_type == 'new_trade_engine':
            trades.append(event.get('data', {}))
        elif event_type == 'daily_equity_engine':
            equity_curve.append(event.get('data', {}))
    
    # 显示交易记录
    print("\n" + "=" * 70)
    print(f"交易记录 ({len(trades)}笔)")
    print("=" * 70)
    
    if trades:
        for i, trade in enumerate(trades):
            date = trade.get('date', '')
            action = trade.get('action', '')
            code = trade.get('code', '')
            shares = trade.get('shares', 0)
            price = trade.get('price', 0)
            amount = trade.get('amount', 0)
            commission = trade.get('commission', 0)
            
            print(f"  {i+1}. {date} {action:4} {code} {shares:5}股 @ {price:7.2f} "
                  f"= {amount:10.2f} (佣金: {commission:.2f})")
    else:
        print("  无交易记录")
    
    # 显示最终结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    if equity_curve:
        initial_equity = equity_curve[0].get('equity', 100000)
        final_equity = equity_curve[-1].get('equity', 100000)
        total_return = (final_equity - initial_equity) / initial_equity
        
        print(f"\n  初始资金: {initial_equity:,.2f}")
        print(f"  最终资金: {final_equity:,.2f}")
        print(f"  策略收益: {total_return:.2%}")
        print(f"  交易次数: {len(trades)}")
        
        buy_count = sum(1 for t in trades if t.get('action') == 'buy')
        sell_count = sum(1 for t in trades if t.get('action') == 'sell')
        print(f"  买入次数: {buy_count}")
        print(f"  卖出次数: {sell_count}")
    
    # 对比聚宽
    print("\n" + "=" * 70)
    print("与聚宽结果对比")
    print("=" * 70)
    print("\n  聚宽结果（2025-01-01 ~ 2025-01-31）:")
    print("    2025-01-21 买入 7800股 @ 11.46")
    print("    2025-01-24 卖出 7800股 @ 11.31")
    print("    1月底总资产: 98688.50")
    print("    收益率: -1.31%")
    
    print("\n  AquaTrade结果（无未来函数）:")
    if equity_curve:
        print(f"    交易次数: {len(trades)}")
        print(f"    1月底总资产: {final_equity:,.2f}")
        print(f"    收益率: {total_return:.2%}")
    
    print("\n  说明:")
    print("    - 聚宽在2025-01-21买入，是因为看到了2025-01-20的金叉")
    print("    - AquaTrade使用相同的逻辑：昨日金叉，今日买入")
    print("    - 两者应该产生相同的交易信号")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
