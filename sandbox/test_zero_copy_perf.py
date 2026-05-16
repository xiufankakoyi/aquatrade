"""
零拷贝架构性能对比测试

对比:
1. 传统方式: Parquet → Polars (每次从磁盘读取)
2. 零拷贝方式: ArcticDB (Arrow) → Polars (内存缓存)
"""
import sys
import os
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
import pyarrow as pa
import arcticdb as adb

from config.config import Config


def test_parquet_read_performance(parquet_path: str, iterations: int = 5):
    """测试 Parquet 读取性能"""
    times = []
    
    for i in range(iterations):
        t0 = time.perf_counter()
        
        df = pl.scan_parquet(parquet_path).filter(
            (pl.col('trade_date') >= '2024-01-01') &
            (pl.col('trade_date') <= '2024-03-31')
        ).collect()
        
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    
    return {
        'method': 'Parquet (磁盘)',
        'avg_time': sum(times) / len(times),
        'min_time': min(times),
        'max_time': max(times),
        'rows': len(df)
    }


def test_arctic_arrow_performance(arctic_uri: str, iterations: int = 5):
    """测试 ArcticDB Arrow 读取性能"""
    arctic = adb.Arctic(arctic_uri)
    
    if 'stock_daily' not in arctic.list_libraries():
        return None
    
    lib = arctic['stock_daily']
    symbols = lib.list_symbols()
    
    if not symbols:
        return None
    
    times = []
    
    for i in range(iterations):
        t0 = time.perf_counter()
        
        all_dfs = []
        for symbol in symbols:
            result = lib.read(symbol)
            arrow_table = result.data
            
            if isinstance(arrow_table, pa.Table):
                df = pl.from_arrow(arrow_table)
            else:
                df = pl.from_pandas(arrow_table)
            
            all_dfs.append(df)
        
        if all_dfs:
            df = pl.concat(all_dfs)
            df = df.filter(
                (pl.col('trade_date') >= '2024-01-01') &
                (pl.col('trade_date') <= '2024-03-31')
            )
        
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    
    return {
        'method': 'ArcticDB Arrow',
        'avg_time': sum(times) / len(times),
        'min_time': min(times),
        'max_time': max(times),
        'rows': len(df) if all_dfs else 0
    }


def test_memory_cache_performance(cached_df: pl.DataFrame, iterations: int = 5):
    """测试内存缓存读取性能"""
    times = []
    
    for i in range(iterations):
        t0 = time.perf_counter()
        
        df = cached_df.filter(
            (pl.col('trade_date') >= '2024-01-01') &
            (pl.col('trade_date') <= '2024-03-31')
        )
        
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    
    return {
        'method': '内存缓存',
        'avg_time': sum(times) / len(times),
        'min_time': min(times),
        'max_time': max(times),
        'rows': len(df)
    }


def test_arctic_write_performance():
    """测试 ArcticDB Arrow 写入性能"""
    arctic = adb.Arctic('lmdb://./data/test_perf_arctic')
    
    if 'test' not in arctic.list_libraries():
        arctic.create_library('test')
    
    lib = arctic['test']
    nvs = lib._nvs
    
    df = pl.DataFrame({
        'trade_date': ['2024-01-15'] * 5000,
        'stock_code': [f'{i:06d}' for i in range(5000)],
        'close': [10.5 + i * 0.01 for i in range(5000)],
        'volume': [1000000 + i * 1000 for i in range(5000)],
    })
    
    arrow_table = df.to_arrow()
    
    times = []
    for i in range(5):
        t0 = time.perf_counter()
        nvs.write(f'test_{i}', arrow_table)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    
    return {
        'method': 'ArcticDB Arrow 写入',
        'avg_time': sum(times) / len(times),
        'rows': len(df)
    }


def test_parquet_write_performance():
    """测试 Parquet 写入性能"""
    df = pl.DataFrame({
        'trade_date': ['2024-01-15'] * 5000,
        'stock_code': [f'{i:06d}' for i in range(5000)],
        'close': [10.5 + i * 0.01 for i in range(5000)],
        'volume': [1000000 + i * 1000 for i in range(5000)],
    })
    
    times = []
    for i in range(5):
        t0 = time.perf_counter()
        df.write_parquet(f'./data/test_perf_{i}.parquet')
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    
    for i in range(5):
        path = f'./data/test_perf_{i}.parquet'
        if os.path.exists(path):
            os.remove(path)
    
    return {
        'method': 'Parquet 写入',
        'avg_time': sum(times) / len(times),
        'rows': len(df)
    }


def main():
    print("=" * 70)
    print("零拷贝架构性能对比测试")
    print("=" * 70)
    
    parquet_dir = Config.PARQUET_DIR
    parquet_path = f"{parquet_dir}/stock_daily.parquet"
    arctic_uri = f"lmdb://{Config.ARCTICDB_PATH}"
    
    print("\n【写入性能测试】")
    print("-" * 70)
    
    write_results = []
    
    arctic_write = test_arctic_write_performance()
    if arctic_write:
        write_results.append(arctic_write)
        print(f"  {arctic_write['method']}: {arctic_write['avg_time']*1000:.2f}ms ({arctic_write['rows']} 行)")
    
    parquet_write = test_parquet_write_performance()
    write_results.append(parquet_write)
    print(f"  {parquet_write['method']}: {parquet_write['avg_time']*1000:.2f}ms ({parquet_write['rows']} 行)")
    
    print("\n【读取性能测试】")
    print("-" * 70)
    
    read_results = []
    
    if os.path.exists(parquet_path):
        parquet_result = test_parquet_read_performance(parquet_path)
        read_results.append(parquet_result)
        print(f"  {parquet_result['method']}: {parquet_result['avg_time']*1000:.2f}ms (avg), {parquet_result['rows']} 行")
    
    arctic_result = test_arctic_arrow_performance(arctic_uri)
    if arctic_result:
        read_results.append(arctic_result)
        print(f"  {arctic_result['method']}: {arctic_result['avg_time']*1000:.2f}ms (avg), {arctic_result['rows']} 行")
    
    if os.path.exists(parquet_path):
        cached_df = pl.read_parquet(parquet_path)
        cache_result = test_memory_cache_performance(cached_df)
        read_results.append(cache_result)
        print(f"  {cache_result['method']}: {cache_result['avg_time']*1000:.2f}ms (avg), {cache_result['rows']} 行")
    
    print("\n【性能对比汇总】")
    print("-" * 70)
    
    if len(read_results) >= 2:
        baseline = read_results[0]['avg_time']
        print(f"\n  读取性能 (相对 Parquet 磁盘读取):")
        for r in read_results:
            speedup = baseline / r['avg_time']
            print(f"    {r['method']}: {r['avg_time']*1000:.2f}ms ({speedup:.1f}x)")
    
    print("\n" + "=" * 70)
    print("结论:")
    print("  - 内存缓存是最快的读取方式 (服务启动时预加载)")
    print("  - ArcticDB Arrow 提供版本控制和增量更新能力")
    print("  - Parquet 作为冷存储备份，支持跨平台共享")
    print("=" * 70)


if __name__ == "__main__":
    main()
