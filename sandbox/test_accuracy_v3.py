"""回测精准性测试 V3 - 详细诊断"""
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
            signals[self.signal_day, 0] = 1
            if self.signal_day + 5 < T:
                signals[self.signal_day + 5, 0] = 2
        
        return signals


def test_accuracy():
    """测试回测精准性"""
    print("\n" + "=" * 70)
    print("回测精准性测试 V3 - 详细诊断")
    print("=" * 70)
    
    config = FastBacktestConfig(
        initial_capital=1000000,
        commission_rate=0.0003
    )
    engine = FastBacktestEngineV2(config)
    strategy = TestStrategy(signal_day=10)
    
    results = list(engine.run_backtest(
        start_date="2023-01-01",
        end_date="2023-03-31",
        strategy=strategy
    ))
    
    print(f"\n交易日数: {len(results)}")
    
    # 找到建仓日
    entry_day = None
    for i, r in enumerate(results):
        if r.positions and entry_day is None:
            entry_day = i
            break
    
    if entry_day is None:
        print("未找到建仓日")
        return
    
    print(f"\n建仓日分析 (第{entry_day}天):")
    
    # 建仓前一日
    prev = results[entry_day - 1]
    print(f"  建仓前一日 ({prev.date.strftime('%Y-%m-%d')}):")
    print(f"    现金: {prev.cash:,.2f}")
    print(f"    持仓: {prev.positions}")
    print(f"    总资产: {prev.total_value:,.2f}")
    
    # 建仓日
    curr = results[entry_day]
    stock_code = list(curr.positions.keys())[0]
    shares = list(curr.positions.values())[0]
    position_value = curr.metrics.get('position_value', 0)
    
    # 计算买入价格
    buy_price = position_value / shares if shares > 0 else 0
    
    print(f"\n  建仓日 ({curr.date.strftime('%Y-%m-%d')}):")
    print(f"    股票代码: {stock_code}")
    print(f"    买入股数: {shares:,.0f}")
    print(f"    持仓市值: {position_value:,.2f}")
    print(f"    推算买入价: {buy_price:.2f}")
    print(f"    现金: {curr.cash:,.2f}")
    print(f"    总资产: {curr.total_value:,.2f}")
    
    # 验证资金守恒
    expected_cash = 1000000 - position_value * (1 + config.commission_rate)
    print(f"\n  资金验证:")
    print(f"    预期现金: {expected_cash:,.2f}")
    print(f"    实际现金: {curr.cash:,.2f}")
    print(f"    差额: {curr.cash - expected_cash:,.2f}")
    
    if abs(curr.cash - expected_cash) > 0.01:
        print(f"    ❌ 资金不守恒!")
    else:
        print(f"    ✅ 资金守恒")


if __name__ == "__main__":
    test_accuracy()
