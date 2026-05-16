"""
简化版性能瓶颈分析
"""
import sys
import os
import time
import cProfile
import pstats
import io
from pstats import SortKey

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
import numpy as np

from config.config import Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3


def analyze_polars_operations():
    """分析 Polars 操作耗时"""
    print("\n" + "=" * 60)
    print("【Polars 操作耗时分析】")
    print("=" * 60)
    
    parquet_dir = Config.PARQUET_DIR
    stock_daily_path = f"{parquet_dir}/stock_daily.parquet"
    stock_info_path = f"{parquet_dir}/stock_info.parquet"
    stock_limit_path = f"{parquet_dir}/stock_limit_status.parquet"
    
    times = {}
    
    t0 = time.perf_counter()
    lazy = pl.scan_parquet(stock_daily_path)
    times['scan_parquet_daily'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    filtered = lazy.filter(
        (pl.col('trade_date') >= '2024-01-01') & 
        (pl.col('trade_date') <= '2024-03-31') &
        (pl.col('total_mv').is_not_null()) &
        (pl.col('volume') > 0)
    )
    times['filter_lazy'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    df = filtered.collect()
    times['collect_daily'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    info = pl.scan_parquet(stock_info_path).collect()
    times['collect_info'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    joined = df.join(info, on='stock_code', how='left')
    times['join'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    limit = pl.scan_parquet(stock_limit_path).filter(
        (pl.col('trade_date') >= '2024-01-01') & 
        (pl.col('trade_date') <= '2024-03-31')
    ).collect()
    times['collect_limit'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    joined2 = joined.join(limit, on=['stock_code', 'trade_date'], how='left')
    times['join_limit'] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    partitions = joined2.partition_by('trade_date', as_dict=True)
    times['partition_by'] = time.perf_counter() - t0
    
    print("\n各环节耗时:")
    total = 0
    for op, t in times.items():
        print(f"  {op}: {t*1000:.1f}ms")
        total += t
    print(f"\n  总计: {total*1000:.1f}ms")
    print(f"  数据量: {len(df)} 行, {len(partitions)} 分区")


def analyze_full_backtest():
    """分析完整回测流程"""
    print("\n" + "=" * 60)
    print("【完整回测流程分析】")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    config = BacktestConfig(initial_capital=1_000_000, commission_rate=0.0003)
    engine = UnifiedBacktestEngine(data_query=data_query, config=config)
    strategy = TrendFollowStrategyV3()
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    t0 = time.perf_counter()
    result = engine.run_backtest(
        strategy=strategy,
        start_date='2024-01-01',
        end_date='2024-03-31',
    )
    
    event_count = 0
    for event in result:
        event_count += 1
        if event.get('type') == 'stream_complete':
            break
    
    total_time = time.perf_counter() - t0
    
    profiler.disable()
    
    print(f"\n回测总耗时: {total_time:.2f}s")
    print(f"事件数: {event_count}")
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(25)
    
    print("\n耗时 Top 25 函数:")
    print(s.getvalue())


def analyze_bottleneck_distribution():
    """分析瓶颈分布"""
    print("\n" + "=" * 60)
    print("【瓶颈分布分析】")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    
    t0 = time.perf_counter()
    data_query.preload_backtest_data('2024-01-01', '2024-03-31')
    data_load_time = time.perf_counter() - t0
    
    config = BacktestConfig(initial_capital=1_000_000, commission_rate=0.0003)
    engine = UnifiedBacktestEngine(data_query=data_query, config=config)
    strategy = TrendFollowStrategyV3()
    
    t0 = time.perf_counter()
    result = engine.run_backtest(
        strategy=strategy,
        start_date='2024-01-01',
        end_date='2024-03-31',
    )
    
    for event in result:
        if event.get('type') == 'stream_complete':
            break
    
    total_time = time.perf_counter() - t0
    backtest_time = total_time - data_load_time
    
    print(f"\n时间分布:")
    print(f"  数据加载: {data_load_time:.2f}s ({data_load_time/total_time*100:.1f}%)")
    print(f"  回测执行: {backtest_time:.2f}s ({backtest_time/total_time*100:.1f}%)")
    print(f"  总计: {total_time:.2f}s")


def main():
    print("=" * 60)
    print("回测系统性能瓶颈分析")
    print("时间范围: 2024-01-01 到 2024-03-31 (约 60 个交易日)")
    print("=" * 60)
    
    analyze_polars_operations()
    analyze_bottleneck_distribution()
    analyze_full_backtest()


if __name__ == "__main__":
    main()
