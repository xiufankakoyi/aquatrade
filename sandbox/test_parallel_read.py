"""
测试 ArcticDB 并行读取性能

对比串行读取和并行读取的性能差异
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_svc.storage.arcticdb_manager import ArcticDBManager


def test_serial_read(lib, symbols: list, limit: int = 100):
    """串行读取"""
    print(f"\n[串行读取] 读取 {limit} 只股票...")
    t0 = time.perf_counter()
    
    all_dfs = []
    for i, sym in enumerate(symbols[:limit]):
        try:
            result = lib.read(sym)
            data = result.data
            if hasattr(data, 'to_pandas'):
                df = pl.from_arrow(data) if hasattr(data, '__arrow_c_array__') else pl.from_pandas(data)
            else:
                df = pl.from_pandas(data)
            if not df.is_empty():
                all_dfs.append(df)
        except Exception as e:
            pass
    
    elapsed = time.perf_counter() - t0
    total_rows = sum(len(df) for df in all_dfs)
    print(f"[串行读取] 完成: {len(all_dfs)} 只股票, {total_rows} 行, 耗时 {elapsed:.2f}s")
    return elapsed, len(all_dfs)


def test_parallel_read(lib, symbols: list, workers: int, limit: int = 100):
    """并行读取"""
    print(f"\n[并行读取-{workers}线程] 读取 {limit} 只股票...")
    t0 = time.perf_counter()
    
    def read_symbol(sym):
        try:
            result = lib.read(sym)
            data = result.data
            if hasattr(data, 'to_pandas'):
                df = pl.from_arrow(data) if hasattr(data, '__arrow_c_array__') else pl.from_pandas(data)
            else:
                df = pl.from_pandas(data)
            return df if not df.is_empty() else None
        except Exception:
            return None
    
    all_dfs = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(read_symbol, sym): sym for sym in symbols[:limit]}
        for future in as_completed(futures):
            df = future.result()
            if df is not None:
                all_dfs.append(df)
    
    elapsed = time.perf_counter() - t0
    total_rows = sum(len(df) for df in all_dfs)
    print(f"[并行读取-{workers}线程] 完成: {len(all_dfs)} 只股票, {total_rows} 行, 耗时 {elapsed:.2f}s")
    return elapsed, len(all_dfs)


def main():
    print("=" * 60)
    print("ArcticDB 并行读取性能测试")
    print("=" * 60)
    
    manager = ArcticDBManager()
    lib = manager._get_or_create_library("daily")
    
    symbols = lib.list_symbols()
    print(f"\n总股票数: {len(symbols)}")
    
    limit = len(symbols)  # 全量读取
    
    serial_time, serial_count = test_serial_read(lib, symbols, limit)
    
    for workers in [5, 10, 20]:
        parallel_time, parallel_count = test_parallel_read(lib, symbols, workers, limit)
        speedup = serial_time / parallel_time if parallel_time > 0 else 0
        print(f"  加速比: {speedup:.2f}x")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
