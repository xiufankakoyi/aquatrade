"""
多策略并行回测性能测试
"""
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.strategies.dual_ma_strategy import DualMAStrategy
from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3
from core.strategies.momentum_strategy import MomentumStrategy
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.backtest.config import BacktestConfig
from data_svc.unified_data_manager import get_unified_manager


def run_single_backtest(strategy, start_date, end_date):
    """运行单个回测"""
    engine = UnifiedBacktestEngine(strategy=strategy, config=BacktestConfig())
    result = engine.run_backtest(start_date=start_date, end_date=end_date)
    return {
        'strategy': strategy.strategy_name,
        'total_return': result.get('total_return', 0),
        'sharpe_ratio': result.get('sharpe_ratio', 0),
        'max_drawdown': result.get('max_drawdown', 0),
        'trades_count': len(result.get('trades', []))
    }


def run_parallel_backtest(strategies, start_date, end_date, max_workers=None):
    """并行运行多个回测"""
    print("=" * 80)
    print(f"并行回测: {len(strategies)} 个策略, {max_workers} 个进程")
    print("=" * 80)
    
    t0 = time.perf_counter()
    
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single_backtest, strategy, start_date, end_date): strategy
            for strategy in strategies
        }
        
        for future in as_completed(futures):
            strategy = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"✓ {result['strategy']} 完成")
            except Exception as e:
                print(f"✗ {strategy.strategy_name} 失败: {e}")
    
    elapsed = time.perf_counter() - t0
    print(f"\n并行回测总耗时: {elapsed:.2f}s")
    print(f"平均每个策略: {elapsed/len(strategies):.2f}s")
    
    return results


def run_sequential_backtest(strategies, start_date, end_date):
    """顺序运行多个回测"""
    print("=" * 80)
    print(f"顺序回测: {len(strategies)} 个策略")
    print("=" * 80)
    
    t0 = time.perf_counter()
    
    results = []
    for strategy in strategies:
        try:
            result = run_single_backtest(strategy, start_date, end_date)
            results.append(result)
            print(f"✓ {result['strategy']} 完成")
        except Exception as e:
            print(f"✗ {strategy.strategy_name} 失败: {e}")
    
    elapsed = time.perf_counter() - t0
    print(f"\n顺序回测总耗时: {elapsed:.2f}s")
    print(f"平均每个策略: {elapsed/len(strategies):.2f}s")
    
    return results


def main():
    print("=" * 80)
    print("多策略回测性能测试")
    print("=" * 80)
    
    start_date = '2024-01-01'
    end_date = '2024-03-31'
    
    print(f"\n回测期间: {start_date} ~ {end_date}")
    
    # 创建策略
    strategies = [
        DualMAStrategy(name='双均线策略_5_10', fast_window=5, slow_window=10),
        DualMAStrategy(name='双均线策略_10_20', fast_window=10, slow_window=20),
        DualMAStrategy(name='双均线策略_20_30', fast_window=20, slow_window=30),
        MomentumStrategy(name='动量策略_5'),
        MomentumStrategy(name='动量策略_10'),
        MomentumStrategy(name='动量策略_20'),
    ]
    
    print(f"\n策略数量: {len(strategies)}")
    for s in strategies:
        print(f"  - {s.strategy_name}")
    
    # 顺序回测
    print("\n" + "=" * 80)
    print("顺序回测")
    print("=" * 80)
    sequential_results = run_sequential_backtest(strategies, start_date, end_date)
    
    # 并行回测
    print("\n" + "=" * 80)
    print("并行回测")
    print("=" * 80)
    parallel_results = run_parallel_backtest(strategies, start_date, end_date, max_workers=4)
    
    # 性能对比
    print("\n" + "=" * 80)
    print("性能对比")
    print("=" * 80)
    
    print("\n顺序回测结果:")
    for r in sequential_results:
        print(f"  {r['strategy']}: "
              f"收益率={r['total_return']:.2%}, "
              f"夏普={r['sharpe_ratio']:.2f}, "
              f"回撤={r['max_drawdown']:.2%}, "
              f"交易={r['trades_count']}")
    
    print("\n并行回测结果:")
    for r in parallel_results:
        print(f"  {r['strategy']}: "
              f"收益率={r['total_return']:.2%}, "
              f"夏普={r['sharpe_ratio']:.2f}, "
              f"回撤={r['max_drawdown']:.2%}, "
              f"交易={r['trades_count']}")
    
    # 加速比
    sequential_time = sum(1 for _ in sequential_results)
    parallel_time = sum(1 for _ in parallel_results)
    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    
    print(f"\n加速比: {speedup:.2f}x")


if __name__ == '__main__':
    main()
