"""
简单回测测试 - 验证优化后的性能
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def main():
    print("=" * 60)
    print("回测性能测试 (2024-2026)")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        min_commission=5.0,
    )
    
    strategy_config = TrendFollowV3Config()
    strategy = TrendFollowStrategyV3(config=strategy_config)
    
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        config=config
    )
    
    start_date = "2024-01-01"
    end_date = "2026-01-31"
    
    print(f"\n开始回测: {start_date} ~ {end_date}")
    
    t0 = time.perf_counter()
    
    result = None
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "stream_complete":
            result = event
            break
    
    t1 = time.perf_counter()
    
    print(f"\n总耗时: {(t1-t0):.2f}s")
    
    if result:
        print(f"回测结果: {result.get('result', {})}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
