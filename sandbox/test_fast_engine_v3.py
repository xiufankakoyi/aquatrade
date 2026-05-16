"""测试极速回测引擎性能 V3 - 优化版纯 NumPy 策略"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
import numpy as np
from typing import List, Optional, Dict

from core.backtest.fast_backtest_engine import FastBacktestEngine, FastBacktestConfig, FastBacktestDailyResult
from core.strategies.vectorized_base import VectorizedStrategyBase


class OptimizedMAStrategy(VectorizedStrategyBase):
    """优化版均线策略 - 使用 cumsum 技巧"""
    strategy_name = "OptimizedMAStrategy"
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        trading_dates: List[str],
        stock_codes: List[str],
        data_query,
        preloaded_data: Optional[Dict] = None
    ) -> np.ndarray:
        """向量化信号生成 - 使用 cumsum 技巧计算 MA"""
        T, N = len(trading_dates), len(stock_codes)
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 提取收盘价
        close = price_matrix[:, :, 3]  # (T, N)
        
        # 使用 cumsum 技巧计算 MA5（比 rolling 快）
        # 处理 NaN：用 0 填充，但记录 mask
        close_filled = np.where(np.isnan(close), 0, close)
        
        # 计算 cumsum
        cumsum = np.cumsum(close_filled, axis=0)
        
        # 计算 MA5
        ma5 = np.zeros_like(close)
        ma5[4:] = (cumsum[4:] - cumsum[:-4]) / 5
        ma5[:4] = cumsum[:4] / np.arange(1, 5).reshape(-1, 1)
        
        # 只在有效数据上计算信号
        valid_mask = ~np.isnan(close)
        
        # 生成信号
        buy_condition = valid_mask & (close > ma5) & (ma5 > 0)
        sell_condition = valid_mask & (close < ma5) & (ma5 > 0)
        
        signal_matrix[buy_condition] = 1
        signal_matrix[sell_condition] = 2
        
        # T+1 逻辑
        signal_matrix[1:] = signal_matrix[:-1]
        signal_matrix[0] = 0
        
        return signal_matrix


def test_fast_engine_v3():
    """测试极速回测引擎 V3"""
    print("\n" + "=" * 70)
    print("极速回测引擎性能测试 V3（优化版纯 NumPy 策略）")
    print("=" * 70)
    
    # 创建引擎
    config = FastBacktestConfig(initial_capital=1000000)
    engine = FastBacktestEngine(config)
    
    # 创建策略
    strategy = OptimizedMAStrategy(None)
    
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
        if not np.isnan(last_result.total_value):
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
    test_fast_engine_v3()
