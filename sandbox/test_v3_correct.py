"""
测试 V3 策略 - 正确的事件类型
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def test_v3():
    print("=" * 80)
    print("测试 V3 策略")
    print("=" * 80)
    
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
    end_date = "2024-03-31"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    
    start_time = time.perf_counter()
    trade_count = 0
    day_count = 0
    
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        event_type = event.get("type")
        
        if event_type == "new_trade_engine":
            trade_count += 1
            data = event.get("data", {})
            if trade_count <= 10:
                print(f"交易 #{trade_count}: {data.get('action')} {data.get('code')} @ {data.get('price')}")
        
        elif event_type == "daily_equity_engine":
            day_count += 1
            if day_count % 10 == 0:
                print(f"已完成 {day_count} 天...")
        
        elif event_type == "stream_complete":
            elapsed = time.perf_counter() - start_time
            data = event.get("data", {})
            
            print(f"\n{'=' * 40}")
            print("V3 策略回测结果")
            print(f"{'=' * 40}")
            print(f"总收益: {data.get('totalReturn', 0):.2f}%")
            print(f"最大回撤: {data.get('maxDrawdown', 0):.2f}%")
            print(f"夏普比率: {data.get('sharpeRatio', 0):.2f}")
            print(f"胜率: {data.get('winRate', 0):.2f}%")
            print(f"交易次数: {trade_count}")
            print(f"基准收益: {data.get('benchmarkReturn', 0):.2f}%")
            print(f"耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    test_v3()
