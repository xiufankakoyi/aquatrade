"""
MA金叉死叉策略测试 - 调试版10
检查交易执行逻辑
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
        
        # 计算金叉死叉 - 只处理2025年的信号
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            if not current_date.startswith('2025'):
                continue
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("MA金叉死叉策略测试 - 调试版10")
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
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print("=" * 70)
    
    results_list = []
    trades_log = []
    signal_days = []
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        results_list.append(event)
        
        if event.get('type') == 'trade':
            trades_log.append(event)
            trade = event.get('trade', {})
            print(f">>> 交易执行: {trade.get('date')} {trade.get('action')} {trade.get('stock_code')}")
    
    # 手动模拟交易执行
    print("\n" + "=" * 70)
    print("手动模拟交易执行")
    print("=" * 70)
    
    test_dates = ['2025-01-23', '2025-04-17', '2025-05-09']
    
    for date_str in test_dates:
        print(f"\n{date_str}:")
        
        # 获取信号
        ts = pd.Timestamp(date_str)
        signals = engine._get_vectorized_signals_for_day(ts)
        print(f"  信号: {signals}")
        
        # 获取 data_dict
        _, _, data_dict = engine._load_day_data(ts)
        
        if '000001' in signals:
            signal = signals['000001']
            action = signal.get('action') if isinstance(signal, dict) else signal
            print(f"  动作: {action}")
            
            if '000001' in data_dict:
                data = data_dict['000001']
                price = data.get('open', 0)
                is_suspended = data.get('is_suspended', 0)
                is_limit_down = data.get('is_limit_down', 0)
                
                print(f"  价格: {price}")
                print(f"  停牌: {is_suspended}")
                print(f"  跌停: {is_limit_down}")
                
                # 检查交易条件
                can_trade = True
                if price <= 0:
                    print(f"  ❌ 价格<=0，无法交易")
                    can_trade = False
                if is_suspended:
                    print(f"  ❌ 停牌，无法交易")
                    can_trade = False
                if is_limit_down and action == 'sell':
                    print(f"  ❌ 跌停，无法卖出")
                    can_trade = False
                
                if can_trade:
                    print(f"  ✅ 可以交易")
    
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
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
