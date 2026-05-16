"""
详细调试交易执行流程
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


class MACrossStrategyDebug(VectorizedStrategyBase):
    """MA金叉死叉策略 - 调试版"""
    
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
print("详细调试交易执行流程")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    
    # 使用自定义配置，设置初始资金为100000
    config = BacktestConfig(
        initial_capital=100000,
        position_ratio=0.95,  # 使用95%的资金
        commission_rate=0.0003,
        min_commission=5.0
    )
    
    engine = UnifiedBacktestEngine(data_query, config=config)
    print(f"  ✓ 初始化完成")
    print(f"  初始资金: {config.initial_capital}")
    print(f"  仓位比例: {config.position_ratio}")

    # 运行回测到第一个买入信号日
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2025-04-30")
    print("=" * 70)
    
    all_events = []
    target_date = '2025-04-17'
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-04-30',
        strategy=strategy
    ):
        all_events.append(event)
        
        # 检查是否到达目标日期
        if event.get('type') == 'daily_equity_engine':
            date = event.get('data', {}).get('date')
            if date == target_date:
                print(f"\n>>> 到达目标日期 {target_date}")
                print(f"    equity={event.get('data', {}).get('equity'):.2f}")
                print(f"    cash={event.get('data', {}).get('cash'):.2f}")
                print(f"    positions={event.get('data', {}).get('positions')}")
    
    # 统计交易
    trades = [e for e in all_events if e.get('type') == 'trade']
    
    print(f"\n[3] 回测完成")
    print(f"   总事件数: {len(all_events)}")
    print(f"   交易数量: {len(trades)}")
    
    if trades:
        print(f"\n   交易记录:")
        for i, trade_event in enumerate(trades):
            trade = trade_event.get('data', {})
            print(f"   {i+1}. {trade.get('date')} {trade.get('action'):4} {trade.get('code')} "
                  f"{trade.get('shares')}股 @ {trade.get('price'):.2f} = {trade.get('amount', 0):.2f}")
    else:
        print(f"\n   ⚠️ 没有交易记录！")
        
        # 手动测试交易执行
        print(f"\n[4] 手动测试交易执行...")
        ts = pd.Timestamp('2025-04-17')
        
        # 获取信号
        signals = engine._get_vectorized_signals_for_day(ts)
        print(f"   信号: {signals}")
        
        # 获取数据
        stock_pool, use_pl, data_dict = engine._load_day_data(ts)
        print(f"   stock_pool类型: {type(stock_pool)}")
        print(f"   data_dict有 {len(data_dict)} 只股票")
        
        # 模拟持仓和现金
        portfolio = {}
        cash = 100000
        position_info = {}
        
        print(f"\n   调用 _execute_trades...")
        print(f"   输入: cash={cash}, portfolio={portfolio}")
        
        new_portfolio, new_cash, trades = engine._execute_trades(
            ts, stock_pool, signals, portfolio, cash, position_info, data_dict
        )
        
        print(f"   输出: new_cash={new_cash}, new_portfolio={new_portfolio}")
        print(f"   交易: {len(trades)}笔")
        
        for trade in trades:
            print(f"      {trade.date} {trade.action} {trade.code} {trade.shares}股 @ {trade.price:.2f}")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
