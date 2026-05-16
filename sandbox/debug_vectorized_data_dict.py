"""
调试向量化模式下的 data_dict
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def debug_vectorized_mode():
    print("=" * 80)
    print("调试向量化模式下的 data_dict")
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
    end_date = "2024-01-05"
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    
    day_count = 0
    for event in engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
    ):
        if event.get("type") == "day_start":
            day_count += 1
            data = event.get("data", {})
            signals = data.get("signals", {})
            data_dict = data.get("data_dict", {})
            
            print(f"\n--- Day {day_count} ---")
            print(f"信号数: {len(signals)}")
            print(f"data_dict 股票数: {len(data_dict)}")
            
            if signals:
                print(f"信号示例: {list(signals.keys())[:5]}")
                missing = [code for code in signals.keys() if code not in data_dict]
                print(f"信号中缺失数据的股票数: {len(missing)}")
                if missing:
                    print(f"缺失示例: {missing[:5]}")
            
        elif event.get("type") == "trade":
            print(f"交易: {event.get('data')}")
        
        elif event.get("type") == "backtest_complete":
            print(f"\n回测完成")


if __name__ == "__main__":
    debug_vectorized_mode()
