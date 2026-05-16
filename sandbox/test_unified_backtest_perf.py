"""
测试 UnifiedDataManager 内存缓存的回测性能

目标：2 年回测时间 < 3s
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

import polars as pl
from loguru import logger


def test_preload_and_backtest():
    """测试预加载和回测性能"""
    print("\n" + "=" * 80)
    print("测试 UnifiedDataManager 内存缓存回测性能")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    print("\n[1/3] 初始化 UnifiedDataManager...")
    t0 = time.perf_counter()
    manager = get_unified_manager()
    elapsed = time.perf_counter() - t0
    print(f"初始化耗时: {elapsed:.2f}s")
    
    print("\n[2/3] 预加载 2 年数据到内存...")
    t0 = time.perf_counter()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    preloaded = manager.preload_to_memory(start_date=start_date, end_date=end_date)
    elapsed = time.perf_counter() - t0
    print(f"预加载耗时: {elapsed:.2f}s")
    
    total_rows = sum(len(df) for df in preloaded.values())
    print(f"预加载行数: {total_rows}")
    
    for lib, df in preloaded.items():
        print(f"  - {lib}: {len(df)} 行")
    
    print("\n[3/3] 运行回测...")
    
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
    
    t0 = time.perf_counter()
    
    events = list(engine.run_backtest(start_date, end_date, strategy))
    
    elapsed = time.perf_counter() - t0
    print(f"\n回测耗时: {elapsed:.2f}s")
    
    final_event = events[-1] if events else None
    if final_event and final_event.get('type') == 'stream_complete':
        result = final_event.get('data', {})
        print(f"\n回测结果:")
        print(f"  - 总收益率: {result.get('totalReturn', 0):.2%}")
        print(f"  - 年化收益: {result.get('annualizedReturn', 0):.2%}")
        print(f"  - 最大回撤: {result.get('maxDrawdown', 0):.2%}")
        print(f"  - 夏普比率: {result.get('sharpeRatio', 0):.2f}")
        print(f"  - 交易次数: {result.get('totalTrades', 0)}")
    
    print("\n" + "=" * 80)
    if elapsed < 3.0:
        print(f"✅ 测试通过! 回测耗时 {elapsed:.2f}s < 3s")
    else:
        print(f"❌ 测试失败! 回测耗时 {elapsed:.2f}s >= 3s")
    print("=" * 80)
    
    return elapsed


def test_data_update_flow():
    """测试数据更新流程"""
    print("\n" + "=" * 80)
    print("测试数据更新流程")
    print("=" * 80)
    
    from update.update_all_stock_data import StockDataUpdater
    
    print("\n[1/2] 初始化数据更新器...")
    try:
        updater = StockDataUpdater()
        print("初始化成功")
    except Exception as e:
        print(f"初始化失败: {e}")
        return False
    
    print("\n[2/2] 测试 ArcticDB 写入...")
    try:
        test_df = pl.DataFrame({
            'trade_date': ['2024-01-15', '2024-01-15'],
            'stock_code': ['000001', '000002'],
            'close': [10.5, 20.3],
            'volume': [1000000, 2000000],
        })
        
        success = updater._write_to_arcticdb('stock_daily', test_df, date_col='trade_date')
        if success:
            print("ArcticDB 写入测试成功")
        else:
            print("ArcticDB 写入测试失败")
        return success
    except Exception as e:
        print(f"写入测试失败: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("UnifiedDataManager 完整测试")
    print("=" * 80)
    
    elapsed = test_preload_and_backtest()
    
    print("\n" + "-" * 80)
    test_data_update_flow()
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)
