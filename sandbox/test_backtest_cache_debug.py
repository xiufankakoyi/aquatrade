"""
诊断回测引擎缓存使用情况
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

import polars as pl


def test_backtest_cache():
    """测试回测引擎缓存使用"""
    print("\n" + "=" * 80)
    print("诊断回测引擎缓存使用")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    print("\n[1] 初始化并预加载数据...")
    manager = get_unified_manager()
    preloaded = manager.preload_to_memory(start_date="2024-01-01", end_date="2025-12-31")
    
    print(f"缓存状态: cache_loaded={manager._cache_loaded}, range={manager._preloaded_date_range}")
    print(f"预加载数据: {[(k, len(v)) for k, v in preloaded.items()]}")
    
    print("\n[2] 测试 get_preloaded_data...")
    test_data = manager.get_preloaded_data("2024-01-01", "2024-01-31")
    for k, v in test_data.items():
        print(f"  {k}: {len(v)} 行")
    
    print("\n[3] 初始化回测引擎...")
    from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
    from core.strategies.trend_follow_v3 import TrendFollowStrategyV3
    from data_svc.database.optimized_data_query import OptimizedStockDataQuery
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        warmup_days=20,
    )
    
    data_query = OptimizedStockDataQuery(warmup=False)
    engine = UnifiedBacktestEngine(config=config, data_query=data_query)
    strategy = TrendFollowStrategyV3()
    
    print("\n[4] 运行回测...")
    t0 = time.perf_counter()
    
    events = list(engine.run_backtest("2024-01-01", "2024-01-31", strategy))
    
    elapsed = time.perf_counter() - t0
    print(f"\n回测耗时: {elapsed:.2f}s")
    
    final_event = events[-1] if events else None
    if final_event and final_event.get('type') == 'stream_complete':
        result = final_event.get('data', {})
        print(f"\n回测结果:")
        print(f"  - 总收益率: {result.get('totalReturn', 0):.2%}")
        print(f"  - 交易次数: {result.get('totalTrades', 0)}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_backtest_cache()
