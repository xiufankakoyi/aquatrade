"""测试极速回测引擎性能"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
import numpy as np
from typing import List, Optional, Dict

from core.backtest.fast_backtest_engine import FastBacktestEngine, FastBacktestConfig, FastBacktestDailyResult
from core.strategies.vectorized_base import VectorizedStrategyBase


class SimpleMAStrategy(VectorizedStrategyBase):
    """简单均线策略 - 用于性能测试"""
    strategy_name = "SimpleMAStrategy"
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        trading_dates: List[str],
        stock_codes: List[str],
        data_query,
        preloaded_data: Optional[Dict] = None
    ) -> np.ndarray:
        """向量化信号生成 - 简单均线策略"""
        T, N = len(trading_dates), len(stock_codes)
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 提取收盘价
        close = price_matrix[:, :, 3]  # (T, N)
        
        # 计算 MA5 - 使用 pandas rolling（C实现）
        import pandas as pd
        close_df = pd.DataFrame(close)
        ma5 = close_df.rolling(window=5, min_periods=1).mean().values
        
        # 生成信号
        buy_condition = (close > ma5) & ~np.isnan(close) & ~np.isnan(ma5)
        sell_condition = (close < ma5) & ~np.isnan(close) & ~np.isnan(ma5)
        
        signal_matrix[buy_condition] = 1
        signal_matrix[sell_condition] = 2
        
        # T+1 逻辑
        signal_matrix[1:] = signal_matrix[:-1]
        signal_matrix[0] = 0
        
        return signal_matrix


def test_fast_engine():
    """测试极速回测引擎"""
    print("\n" + "=" * 70)
    print("极速回测引擎性能测试")
    print("=" * 70)
    
    # 创建引擎
    config = FastBacktestConfig(initial_capital=1000000)
    engine = FastBacktestEngine(config)
    
    # 创建策略
    strategy = SimpleMAStrategy(None)
    
    # 执行回测
    print("\n开始回测...")
    t_start = time.perf_counter()
    
    results = list(engine.run_backtest(
        start_date="2023-01-01",
        end_date="2023-12-31",
        strategy=strategy
    ))
    
    t_end = time.perf_counter()
    total_time = (t_end - t_start) * 1000
    
    print("\n" + "=" * 70)
    print("性能结果:")
    print(f"  总耗时: {total_time:.1f}ms")
    print(f"  交易日数: {len(results)}")
    
    if len(results) > 0:
        first_result = results[0]
        last_result = results[-1]
        print(f"  初始资金: {config.initial_capital:,.0f}")
        print(f"  最终资金: {last_result.total_value:,.0f}")
        print(f"  收益率: {(last_result.total_value / config.initial_capital - 1) * 100:.2f}%")
    
    print("\n" + "=" * 70)
    print("目标对比:")
    print(f"  目标: < 1000ms")
    print(f"  实际: {total_time:.1f}ms")
    
    if total_time < 1000:
        print(f"  状态: ✅ 达标")
    else:
        print(f"  状态: ❌ 未达标 (差距: {total_time - 1000:.1f}ms)")
        print(f"  需要优化: {total_time / 1000:.1f}x")
    print("=" * 70)


if __name__ == "__main__":
    test_fast_engine()
