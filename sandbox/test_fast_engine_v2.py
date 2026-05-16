"""测试极速回测引擎性能 V2 - 纯 NumPy 策略"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
import numpy as np
from typing import List, Optional, Dict

from core.backtest.fast_backtest_engine import FastBacktestEngine, FastBacktestConfig, FastBacktestDailyResult
from core.strategies.vectorized_base import VectorizedStrategyBase


class PureNumpyMAStrategy(VectorizedStrategyBase):
    """纯 NumPy 均线策略 - 极致性能"""
    strategy_name = "PureNumpyMAStrategy"
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        trading_dates: List[str],
        stock_codes: List[str],
        data_query,
        preloaded_data: Optional[Dict] = None
    ) -> np.ndarray:
        """向量化信号生成 - 纯 NumPy 实现（无 Pandas）"""
        T, N = len(trading_dates), len(stock_codes)
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 提取收盘价
        close = price_matrix[:, :, 3]  # (T, N)
        
        # 纯 NumPy 计算 MA5（比 Pandas 快 2-3 倍）
        # 使用卷积计算移动平均
        kernel = np.ones(5) / 5
        
        # 对每个股票计算 MA5
        ma5 = np.zeros_like(close)
        for i in range(N):
            col = close[:, i]
            # 使用 cumsum 技巧计算移动平均（避免边界问题）
            valid_mask = ~np.isnan(col)
            if valid_mask.any():
                valid_col = col[valid_mask]
                if len(valid_col) >= 5:
                    # 使用卷积
                    ma5_valid = np.convolve(valid_col, kernel, mode='valid')
                    # 填充前4个值
                    ma5[:4, i] = np.nan
                    ma5[4:, i] = ma5_valid
                else:
                    # 数据不足，使用简单平均
                    ma5[:, i] = np.nanmean(valid_col)
        
        # 生成信号
        buy_condition = (close > ma5) & ~np.isnan(close) & ~np.isnan(ma5)
        sell_condition = (close < ma5) & ~np.isnan(close) & ~np.isnan(ma5)
        
        signal_matrix[buy_condition] = 1
        signal_matrix[sell_condition] = 2
        
        # T+1 逻辑
        signal_matrix[1:] = signal_matrix[:-1]
        signal_matrix[0] = 0
        
        return signal_matrix


def test_fast_engine_v2():
    """测试极速回测引擎 V2"""
    print("\n" + "=" * 70)
    print("极速回测引擎性能测试 V2（纯 NumPy 策略）")
    print("=" * 70)
    
    # 创建引擎
    config = FastBacktestConfig(initial_capital=1000000)
    engine = FastBacktestEngine(config)
    
    # 创建策略
    strategy = PureNumpyMAStrategy(None)
    
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
    test_fast_engine_v2()
