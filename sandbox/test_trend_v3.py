"""
测试向量化策略 V3 - 验证声明式因子系统

目标：
1. 验证 prepare_data() 自动注入因子
2. 验证策略逻辑正确
3. 对比 V2 和 V3 的性能
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v2 import TrendFollowStrategyV2, TrendFollowV2Config
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def test_v3_strategy():
    """测试 V3 策略"""
    print("=" * 80)
    print("测试向量化策略 V3 - 声明式因子系统")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        min_commission=5.0,
    )
    
    strategy_config = TrendFollowV3Config(
        bias_threshold_high=0.10,
        stop_loss_pct=0.10,
        trailing_stop_pct=0.08,
        volume_ratio_min=1.5,
    )
    
    strategy = TrendFollowStrategyV3(config=strategy_config)
    
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        config=config
    )
    
    start_date = "2024-01-01"
    end_date = "2024-03-31"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print("运行中...\n")
    
    start_time = time.perf_counter()
    
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "backtest_complete":
            metrics = event.get("metrics", {})
            elapsed = time.perf_counter() - start_time
            
            print(f"\n{'=' * 40}")
            print("V3 策略回测结果")
            print(f"{'=' * 40}")
            print(f"总收益: {metrics.get('totalReturn', 0):.2f}%")
            print(f"最大回撤: {metrics.get('maxDrawdown', 0):.2f}%")
            print(f"夏普比率: {metrics.get('sharpeRatio', 0):.2f}")
            print(f"胜率: {metrics.get('winRate', 0):.2f}%")
            print(f"交易次数: {metrics.get('tradeCount', 0)}")
            print(f"耗时: {elapsed:.2f}s")
            
            return metrics, elapsed
    
    return None, 0


def test_v2_strategy():
    """测试 V2 策略（对比基准）"""
    print("\n" + "=" * 80)
    print("测试 V2 策略（对比基准）")
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
    end_date = "2024-03-31"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print("运行中...\n")
    
    start_time = time.perf_counter()
    
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "backtest_complete":
            metrics = event.get("metrics", {})
            elapsed = time.perf_counter() - start_time
            
            print(f"\n{'=' * 40}")
            print("V2 策略回测结果")
            print(f"{'=' * 40}")
            print(f"总收益: {metrics.get('totalReturn', 0):.2f}%")
            print(f"最大回撤: {metrics.get('maxDrawdown', 0):.2f}%")
            print(f"夏普比率: {metrics.get('sharpeRatio', 0):.2f}")
            print(f"胜率: {metrics.get('winRate', 0):.2f}%")
            print(f"交易次数: {metrics.get('tradeCount', 0)}")
            print(f"耗时: {elapsed:.2f}s")
            
            return metrics, elapsed
    
    return None, 0


def main():
    print("\n" + "=" * 80)
    print("声明式因子系统验证测试")
    print("=" * 80)
    
    v3_metrics, v3_time = test_v3_strategy()
    v2_metrics, v2_time = test_v2_strategy()
    
    print("\n" + "=" * 80)
    print("性能对比")
    print("=" * 80)
    
    if v3_metrics and v2_metrics:
        print(f"\n{'指标':<20} {'V2':<15} {'V3':<15} {'变化':<15}")
        print("-" * 65)
        print(f"{'耗时':<20} {v2_time:<15.2f} {v3_time:<15.2f} {(v3_time/v2_time-1)*100:+.1f}%")
        print(f"{'总收益':<20} {v2_metrics.get('totalReturn', 0):<15.2f} {v3_metrics.get('totalReturn', 0):<15.2f}")
        print(f"{'最大回撤':<20} {v2_metrics.get('maxDrawdown', 0):<15.2f} {v3_metrics.get('maxDrawdown', 0):<15.2f}")
        print(f"{'夏普比率':<20} {v2_metrics.get('sharpeRatio', 0):<15.2f} {v3_metrics.get('sharpeRatio', 0):<15.2f}")
        print(f"{'交易次数':<20} {v2_metrics.get('tradeCount', 0):<15} {v3_metrics.get('tradeCount', 0):<15}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
