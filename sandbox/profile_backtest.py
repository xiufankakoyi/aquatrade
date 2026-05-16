"""
回测性能分析脚本

使用 cProfile 定位性能热点
"""
import cProfile
import pstats
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v2 import TrendFollowStrategyV2, TrendFollowV2Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def run_backtest_for_profile():
    """运行回测用于性能分析"""
    print("=" * 80)
    print("回测性能分析")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        min_commission=5.0,
    )
    
    strategy_config = TrendFollowV2Config(
        bias_threshold_high=0.10,
        stop_loss_pct=0.10,
        trailing_stop_pct=0.08,
        volume_ratio_min=1.5,
    )
    
    strategy = TrendFollowStrategyV2(config=strategy_config)
    
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        config=config
    )
    
    start_date = "2024-01-01"
    end_date = "2024-06-30"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print("运行中...")
    
    final_result = None
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "backtest_complete":
            final_result = event.get("data", {})
    
    if final_result:
        print(f"\n结果:")
        print(f"  总收益: {final_result.get('totalReturn', 0):.2f}%")
        print(f"  最大回撤: {final_result.get('maxDrawdown', 0):.2f}%")
    
    return final_result


def profile_backtest():
    """使用 cProfile 分析回测性能"""
    profiler = cProfile.Profile()
    
    print("\n" + "=" * 80)
    print("开始 cProfile 性能分析")
    print("=" * 80)
    
    profiler.enable()
    run_backtest_for_profile()
    profiler.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    
    print("\n" + "=" * 80)
    print("性能热点分析 (按累计时间排序)")
    print("=" * 80)
    
    ps.print_stats(50)
    print(s.getvalue())
    
    print("\n" + "=" * 80)
    print("性能热点分析 (按自身时间排序)")
    print("=" * 80)
    
    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2).sort_stats('time')
    ps2.print_stats(30)
    print(s2.getvalue())
    
    profiler.dump_stats("sandbox/profile_results.prof")
    print("\n详细结果已保存到: sandbox/profile_results.prof")
    print("可使用 snakeviz 查看: snakeviz sandbox/profile_results.prof")


if __name__ == "__main__":
    profile_backtest()
