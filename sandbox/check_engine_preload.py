"""
检查回测引擎预加载是否被触发
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v2 import TrendFollowStrategyV2, TrendFollowV2Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_engine_preload():
    print("=" * 80)
    print("检查回测引擎预加载")
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
    end_date = "2024-01-10"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print("运行中...")
    
    event_count = 0
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        event_count += 1
        if event.get("type") == "backtest_complete":
            print(f"\n回测完成")
    
    # 检查预加载数据
    print(f"\n预加载数据状态:")
    print(f"  _preloaded_data 是否存在: {data_query._preloaded_data is not None}")
    if data_query._preloaded_data:
        print(f"  预加载日期数: {len(data_query._preloaded_data)}")
        print(f"  预加载日期范围: {data_query._preloaded_date_range}")

if __name__ == "__main__":
    check_engine_preload()
