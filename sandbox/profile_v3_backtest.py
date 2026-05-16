"""
使用 cProfile 分析 V3 策略回测性能
时间跨度: 2024-01-01 ~ 2026-01-31
"""
import sys
import cProfile
import pstats
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def run_backtest():
    """运行回测（用于性能分析）"""
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
    
    trade_count = 0
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        event_type = event.get("type")
        if event_type == "new_trade_engine":
            trade_count += 1
        elif event_type == "stream_complete":
            data = event.get("data", {})
            print(f"\n总收益: {data.get('totalReturn', 0):.2f}%")
            print(f"交易次数: {trade_count}")


def main():
    print("=" * 80)
    print("cProfile 性能分析: V3 策略回测 (2024-2026)")
    print("=" * 80)
    
    profiler = cProfile.Profile()
    
    profiler.enable()
    run_backtest()
    profiler.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    
    print("\n" + "=" * 80)
    print("性能分析结果 (按累计时间排序)")
    print("=" * 80)
    
    ps.print_stats(50)
    print(s.getvalue())
    
    print("\n" + "=" * 80)
    print("性能分析结果 (按自身时间排序)")
    print("=" * 80)
    
    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2).sort_stats('time')
    ps2.print_stats(30)
    print(s2.getvalue())


if __name__ == "__main__":
    main()
