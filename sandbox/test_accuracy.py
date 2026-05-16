"""回测精准性测试 - 验证交易逻辑的正确性"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

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
    print("回测精准性测试")
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
        end_date="2023-03-31",  # 短周期测试
        strategy=strategy
    ))
    
    print(f"\n回测结果:")
    print(f"  交易日数: {len(results)}")
    
    if len(results) > 0:
        first = results[0]
        last = results[-1]
        
        print(f"\n首日 ({first.date.strftime('%Y-%m-%d')}):")
        print(f"  总资产: {first.total_value:,.2f}")
        print(f"  现金: {first.cash:,.2f}")
        print(f"  持仓: {first.positions}")
        
        print(f"\n末日 ({last.date.strftime('%Y-%m-%d')}):")
        print(f"  总资产: {last.total_value:,.2f}")
        print(f"  现金: {last.cash:,.2f}")
        print(f"  持仓: {last.positions}")
        
        # 验证资金守恒
        print(f"\n资金守恒验证:")
        for i, r in enumerate(results):
            position_value = sum(r.positions.values())
            expected_total = r.cash + position_value
            if abs(r.total_value - expected_total) > 0.01:
                print(f"  ❌ 第{i}天资金不守恒: {r.total_value:.2f} != {expected_total:.2f}")
                return False
        print("  ✅ 所有日期资金守恒")
        
        # 验证持仓变化
        print(f"\n持仓变化验证:")
        has_position = False
        for i, r in enumerate(results):
            if r.positions:
                if not has_position:
                    print(f"  第{i}天首次建仓: {r.positions}")
                    has_position = True
            else:
                if has_position:
                    print(f"  第{i}天清仓")
                    has_position = False
        
        print("\n✅ 精准性测试通过")
        return True


if __name__ == "__main__":
    test_accuracy()
