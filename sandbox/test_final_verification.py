"""
最终验证 - MA金叉死叉策略回测
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
print("MA金叉死叉策略 - 最终验证")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyFinal(stock_code='000001')
    
    # 使用自定义配置
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
    
    # 提取交易记录 (注意事件类型是 'new_trade_engine')
    trades = []
    equity_curve = []
    dividends = []
    
    for event in all_events:
        event_type = event.get('type', '')
        if event_type == 'new_trade_engine':
            trades.append(event.get('data', {}))
        elif event_type == 'daily_equity_engine':
            equity_curve.append(event.get('data', {}))
        elif event_type == 'dividend_payout':
            dividends.append(event.get('data', {}))
    
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
            profit_loss = trade.get('profitLoss', 0) or trade.get('profit_loss', 0)
            
            if action == 'buy':
                print(f"  {i+1}. {date} {action:4} {code} {shares:5}股 @ {price:7.2f} "
                      f"= {amount:10.2f} (佣金: {commission:.2f})")
            else:
                print(f"  {i+1}. {date} {action:4} {code} {shares:5}股 @ {price:7.2f} "
                      f"= {amount:10.2f} (盈亏: {profit_loss:+.2f})")
    else:
        print("  无交易记录")
    
    # 显示分红记录
    if dividends:
        print("\n" + "=" * 70)
        print(f"分红记录 ({len(dividends)}笔)")
        print("=" * 70)
        for i, div in enumerate(dividends):
            print(f"  {i+1}. {div.get('date')}: {div.get('code')} 现金分红 {div.get('dividend', 0):.2f}")
    
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
        print(f"  分红次数: {len(dividends)}")
        
        # 计算买入和卖出次数
        buy_count = sum(1 for t in trades if t.get('action') == 'buy')
        sell_count = sum(1 for t in trades if t.get('action') == 'sell')
        print(f"  买入次数: {buy_count}")
        print(f"  卖出次数: {sell_count}")
        
        # 计算胜率
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        if sell_trades:
            win_count = sum(1 for t in sell_trades 
                          if (t.get('profitLoss', 0) or t.get('profit_loss', 0) or 0) > 0)
            win_rate = win_count / len(sell_trades)
            print(f"  胜率: {win_rate:.1%} ({win_count}/{len(sell_trades)})")
    
    print("\n" + "=" * 70)
    print("回测完成!")
    print("=" * 70)
    
    # 与聚宽结果对比
    print("\n" + "=" * 70)
    print("与聚宽结果对比")
    print("=" * 70)
    print("\n  聚宽结果:")
    print("    策略收益: 5.24%")
    print("    基准收益: 17.66%")
    print("    交易次数: 未明确")
    print("\n  AquaTrade结果:")
    if equity_curve:
        print(f"    策略收益: {total_return:.2%}")
        print(f"    交易次数: {len(trades)}")
    
    print("\n  说明:")
    print("    - 两者收益差异可能是由于不同的手续费、滑点、分红处理等因素")
    print("    - 聚宽可能使用了不同的初始资金或仓位管理策略")
    print("    - 建议检查聚宽策略的具体参数设置")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
