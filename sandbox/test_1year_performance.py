"""
一年数据回测性能测试
目标：一年数据回测 < 1000ms
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

def test_1year_ma_strategy():
    """测试一年数据简单均线策略性能"""
    print("\n" + "=" * 70)
    print("一年数据简单均线策略性能测试")
    print("=" * 70)
    
    from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
    from core.strategies.vectorized_base import VectorizedStrategyBase
    from core.strategies.jq_volume_strategy_v2 import JQVolumeConfigpro
    from data_svc.database.optimized_data_query import OptimizedStockDataQuery
    
    class SimpleMAStrategy(VectorizedStrategyBase):
        """简单均线策略 - 用于性能测试"""
        strategy_name = "SimpleMAStrategy"
        
        def generate_signals_vectorized(
            self,
            price_matrix: np.ndarray,
            trading_dates: List[str],
            stock_codes: List[str],
            data_query,
            preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
        ) -> np.ndarray:
            """向量化信号生成 - 简单均线策略"""
            T, N = len(trading_dates), len(stock_codes)
            signal_matrix = np.zeros((T, N), dtype=np.int32)
            
            if preloaded_data is None or len(preloaded_data) == 0:
                return signal_matrix
            
            # 准备数据
            self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
            
            # 简单策略：收盘价 > MA5 买入，< MA5 卖出
            close = self.close
            
            # 计算 MA5 - 使用 pandas rolling（C实现）
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
    
    # 创建数据查询对象
    data_query = OptimizedStockDataQuery()
    
    # 创建回测配置
    config = BacktestConfig(
        initial_capital=1000000
    )
    
    # 创建回测引擎
    engine = UnifiedBacktestEngine(data_query, config)
    
    # 创建策略
    strategy_config = JQVolumeConfigpro(max_stocks_per_day=10)
    strategy = SimpleMAStrategy(strategy_config)
    
    # 执行回测 - 一年数据
    t_start = time.perf_counter()
    result = list(engine.run_backtest(
        start_date="2023-01-01",
        end_date="2023-12-31",
        strategy=strategy
    ))
    t_end = time.perf_counter()
    
    total_elapsed = (t_end - t_start) * 1000
    
    # 获取交易日数量
    trading_dates = data_query.get_trading_dates("2023-01-01", "2023-12-31")
    
    print(f"\n回测参数:")
    print(f"      开始日期: 2023-01-01")
    print(f"      结束日期: 2023-12-31")
    print(f"      交易日数: {len(trading_dates)}")
    
    print(f"\n性能结果:")
    print(f"      总耗时: {total_elapsed:.1f}ms ({total_elapsed/1000:.2f}s)")
    print(f"      平均每日: {total_elapsed/len(trading_dates):.2f}ms")
    
    # 打印缓存统计
    from core.strategies.vectorized_base import get_matrix_cache_stats
    cache_stats = get_matrix_cache_stats()
    print(f"\n缓存统计:")
    print(f"      命中: {cache_stats['hits']}")
    print(f"      未命中: {cache_stats['misses']}")
    print(f"      命中率: {cache_stats['hit_rate']:.1f}%")
    
    # 目标对比
    target = 1000  # 目标 1000ms
    print(f"\n目标对比:")
    print(f"      目标: < {target}ms")
    print(f"      实际: {total_elapsed:.1f}ms")
    if total_elapsed <= target:
        print(f"      状态: ✅ 达标")
    else:
        print(f"      状态: ❌ 未达标 (差距: {total_elapsed - target:.1f}ms)")
        print(f"      需要优化: {total_elapsed/target:.1f}x")
    
    return total_elapsed

if __name__ == "__main__":
    test_1year_ma_strategy()
