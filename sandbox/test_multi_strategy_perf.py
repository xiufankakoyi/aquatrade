"""
多策略性能测试 - 简化版
只测试两个已知有效的策略
"""
import sys
import time
import cProfile
import pstats
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import Config
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from core.strategies.dual_ma_strategy import DualMAStrategy
from data_svc.unified_data_manager import get_unified_manager

def run_backtest(strategy, strategy_name: str, preloaded: bool = False):
    """
    运行单个策略的回测
    """
    print(f"\n{'='*60}")
    print(f"测试策略: {strategy_name}")
    print(f"{'='*60}")
    
    if not preloaded:
        manager = get_unified_manager()
        manager.preload_to_memory(start_date='2024-01-01', end_date='2024-03-31')
    
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
    )
    
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        config=config
    )
    
    t0 = time.perf_counter()
    event_count = 0
    trades = 0
    final_equity = 0
    
    result = engine.run_backtest(
        strategy=strategy,
        start_date='2024-01-01',
        end_date='2024-03-31',
    )
    
    for event in result:
        event_count += 1
        if event.get('type') == 'final_metrics':
            final_equity = event.get('data', {}).get('final_equity', 0)
        elif event.get('type') == 'daily_equity_engine':
            trades = event.get('data', {}).get('total_trades', 0)
    
    total_time = time.perf_counter() - t0
    
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  事件数: {event_count}")
    print(f"  最终权益: {final_equity:,.0f}")
    print(f"  交易次数: {trades}")
    
    return {
        'strategy': strategy_name,
        'total_time': total_time,
        'final_equity': final_equity,
        'trades': trades,
        'events': event_count,
    }

def profile_strategy(strategy, strategy_name: str):
    """
    对单个策略进行详细性能分析
    """
    print(f"\n{'='*60}")
    print(f"详细性能分析: {strategy_name}")
    print(f"{'='*60}")
    
    manager = get_unified_manager()
    if not manager._cache_loaded:
        manager.preload_to_memory(start_date='2024-01-01', end_date='2024-03-31')
    
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
    )
    
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        config=config
    )
    
    pr = cProfile.Profile()
    pr.enable()
    
    result = engine.run_backtest(
        strategy=strategy,
        start_date='2024-01-01',
        end_date='2024-03-31',
    )
    
    for event in result:
        pass
    
    pr.disable()
    
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(40)
    
    print(s.getvalue())

def main():
    print("=" * 60)
    print("多策略性能测试")
    print("时间范围: 2024-01-01 到 2024-03-31 (约 60 个交易日)")
    print("=" * 60)
    
    strategies = [
        (TrendFollowStrategyV3(config=TrendFollowV3Config()), 'TrendFollowStrategyV3'),
        (DualMAStrategy(), 'DualMAStrategy'),
    ]
    
    results = []
    
    for i, (strategy, name) in enumerate(strategies):
        result = run_backtest(strategy, name, preloaded=(i > 0))
        results.append(result)
    
    print("\n" + "=" * 60)
    print("性能汇总")
    print("=" * 60)
    print(f"{'策略':<30} {'耗时(s)':<12} {'交易次数':<12} {'事件数':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['strategy']:<30} {r['total_time']:<12.2f} {r['trades']:<12} {r['events']:<10}")
    
    if results:
        fastest = min(results, key=lambda x: x['total_time'])
        slowest = max(results, key=lambda x: x['total_time'])
        print(f"\n最快策略: {fastest['strategy']} ({fastest['total_time']:.2f}s)")
        print(f"最慢策略: {slowest['strategy']} ({slowest['total_time']:.2f}s)")
        
        print("\n" + "=" * 60)
        print("对最慢策略进行详细分析...")
        print("=" * 60)
        for strategy, name in strategies:
            if name == slowest['strategy']:
                profile_strategy(strategy, name)
                break

if __name__ == '__main__':
    main()
