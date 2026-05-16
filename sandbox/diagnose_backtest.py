"""
诊断回测问题
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
    print("诊断回测问题")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2026-01-31"
    
    print(f"\n[1] 获取交易日期: {start_date} ~ {end_date}")
    trading_dates = data_query.get_trading_dates(start_date, end_date)
    print(f"    交易日数量: {len(trading_dates)}")
    if trading_dates:
        print(f"    第一个: {trading_dates[0]}")
        print(f"    最后一个: {trading_dates[-1]}")
    
    print(f"\n[2] 预加载数据")
    data_query.preload_backtest_data(start_date, end_date)
    preloaded = data_query._preloaded_data
    print(f"    预加载天数: {len(preloaded) if preloaded else 0}")
    
    if preloaded:
        dates_in_preloaded = sorted(preloaded.keys())
        print(f"    预加载日期范围: {dates_in_preloaded[0]} ~ {dates_in_preloaded[-1]}")
    
    print(f"\n[3] 运行回测")
    
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
    
    day_count = 0
    t0 = time.perf_counter()
    
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "backtest_start":
            print(f"    回测开始: {event}")
        elif event.get("type") == "day_complete":
            day_count += 1
            if day_count <= 5 or day_count % 100 == 0:
                print(f"    Day {day_count}: {event.get('data', {}).get('date', 'N/A')}")
        elif event.get("type") == "stream_complete":
            print(f"    回测完成: {event}")
            break
    
    t1 = time.perf_counter()
    
    print(f"\n总耗时: {(t1-t0):.2f}s")
    print(f"处理天数: {day_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
