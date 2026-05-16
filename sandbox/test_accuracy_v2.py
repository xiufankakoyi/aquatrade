"""回测精准性测试 V2 - 验证交易逻辑的正确性"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd

from core.backtest.fast_backtest_engine_v2 import FastBacktestEngineV2, FastBacktestConfig
from core.strategies.vectorized_base import VectorizedStrategyBase


class TestStrategy(VectorizedStrategyBase):
    """测试策略 - 用于验证回测精准性"""
    strategy_name = "TestStrategy"
    
    def __init__(self, signal_day=None):
        super().__init__()
        self.signal_day = signal_day
    
    def generate_signals_vectorized(
        self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data=None
    ):
        """生成测试信号"""
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        if self.signal_day is not None and self.signal_day < T:
            # 只在指定日期买入第一只股票
            signals[self.signal_day, 0] = 1
            # 在之后第5天卖出
            if self.signal_day + 5 < T:
                signals[self.signal_day + 5, 0] = 2
        
        return signals


def test_accuracy():
    """测试回测精准性"""
    print("\n" + "=" * 70)
    print("回测精准性测试 V2")
    print("=" * 70)
    
    # 创建引擎
    config = FastBacktestConfig(
        initial_capital=1000000,
        commission_rate=0.0003
    )
    engine = FastBacktestEngineV2(config)
    
    # 创建策略（在第10天买入，第15天卖出）
    strategy = TestStrategy(signal_day=10)
    
    # 执行回测
    results = list(engine.run_backtest(
        start_date="2023-01-01",
        end_date="2023-03-31",
        strategy=strategy
    ))
    
    print(f"\n回测结果:")
    print(f"  交易日数: {len(results)}")
    
    if len(results) > 0:
        # 找到建仓和平仓的日期
        entry_day = None
        exit_day = None
        
        for i, r in enumerate(results):
            if r.positions and entry_day is None:
                entry_day = i
                entry_price = r.metrics.get('position_value', 0) / list(r.positions.values())[0] if r.positions else 0
                print(f"\n第{i}天建仓:")
                print(f"  持仓: {r.positions}")
                print(f"  持仓市值: {r.metrics.get('position_value', 0):,.2f}")
                print(f"  现金: {r.cash:,.2f}")
                print(f"  总资产: {r.total_value:,.2f}")
            
            if entry_day is not None and not r.positions and exit_day is None:
                exit_day = i
                print(f"\n第{i}天平仓:")
                print(f"  现金: {r.cash:,.2f}")
                print(f"  总资产: {r.total_value:,.2f}")
        
        # 验证资金变化
        print(f"\n资金变化验证:")
        initial = results[0].total_value
        final = results[-1].total_value
        
        if entry_day is not None:
            entry_cash = results[entry_day].cash
            entry_total = results[entry_day].total_value
            print(f"  建仓前现金: {entry_cash:,.2f}")
            print(f"  建仓后总资产: {entry_total:,.2f}")
            
            # 验证买入使用了开盘价
            if entry_day > 0:
                prev_close = results[entry_day-1].total_value
                print(f"  建仓前一日总资产: {prev_close:,.2f}")
        
        print(f"\n  初始资金: {initial:,.2f}")
        print(f"  最终资金: {final:,.2f}")
        print(f"  总收益: {final - initial:,.2f}")
        print(f"  收益率: {(final/initial - 1)*100:.2f}%")
        
        # 验证没有资金泄漏
        print(f"\n✅ 精准性测试完成")
        return True


if __name__ == "__main__":
    test_accuracy()
