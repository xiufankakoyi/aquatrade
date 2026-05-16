"""
数据库读取性能对比测试

对比 ArcticDB (LMDB)、DuckDB、Parquet 的读取性能

测试步骤：
1. 从 ArcticDB 导出数据到 Parquet
2. 对比各存储方式的读取性能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl
from concurrent.futures import ThreadPoolExecutor, as_completed

print("=" * 70)
print("数据库读取性能对比测试")
print("=" * 70)


def export_to_parquet(limit: int = 1000):
    """从 ArcticDB 导出数据到 Parquet"""
    print(f"\n[导出] 从 ArcticDB 导出 {limit} 只股票数据到 Parquet...")
    
    from data_svc.storage.arcticdb_manager import ArcticDBManager
    
    manager = ArcticDBManager()
    lib = manager._get_or_create_library("daily")
    
    symbols = lib.list_symbols()[:limit]
    print(f"股票数量: {len(symbols)}")
    
    parquet_dir = Path(__file__).parent.parent / "data" / "parquet_benchmark"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    
    t0 = time.perf_counter()
    
    all_dfs = []
    for i, sym in enumerate(symbols):
        try:
            result = lib.read(sym)
            data = result.data
            if hasattr(data, '__arrow_c_array__'):
                df = pl.from_arrow(data)
            else:
                df = pl.from_pandas(data)
            if not df.is_empty():
                all_dfs.append(df)
        except Exception:
            pass
        
        if (i + 1) % 1000 == 0:
            print(f"  已读取 {i + 1}/{len(symbols)} 只股票...")
    
    if all_dfs:
        normalized_dfs = []
        for df in all_dfs:
            int_cols = [c for c in df.columns 
                       if df.schema[c] in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, 
                                           pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)]
            if int_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64) for c in int_cols])
            normalized_dfs.append(df)
        
        combined = pl.concat(normalized_dfs, how='diagonal')
        output_path = parquet_dir / "daily_all.parquet"
        combined.write_parquet(output_path, compression='snappy')
        
        elapsed = time.perf_counter() - t0
        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"[导出] 完成: {output_path}")
        print(f"[导出] 数据量: {len(combined):,} 行, 文件大小: {file_size:.1f} MB")
        print(f"[导出] 耗时: {elapsed:.2f}s")
        
        return output_path, len(combined)
    
    return None, 0


def test_arcticdb_serial(symbols_limit: int = None):
    """测试 ArcticDB 串行读取"""
    print("\n" + "-" * 70)
    print("[ArcticDB] 串行读取测试")
    print("-" * 70)
    
    from data_svc.storage.arcticdb_manager import ArcticDBManager
    
    manager = ArcticDBManager()
    lib = manager._get_or_create_library("daily")
    
    symbols = lib.list_symbols()
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    
    print(f"股票数量: {len(symbols)}")
    
    t0 = time.perf_counter()
    all_dfs = []
    for sym in symbols:
        try:
            result = lib.read(sym)
            data = result.data
            if hasattr(data, '__arrow_c_array__'):
                df = pl.from_arrow(data)
            else:
                df = pl.from_pandas(data)
            if not df.is_empty():
                all_dfs.append(df)
        except Exception:
            pass
    
    elapsed = time.perf_counter() - t0
    total_rows = sum(len(df) for df in all_dfs)
    print(f"[ArcticDB-串行] 完成: {len(all_dfs)} 只股票, {total_rows:,} 行, 耗时 {elapsed:.2f}s")
    
    return elapsed, total_rows


def test_arcticdb_parallel(symbols_limit: int = None, workers: int = 5):
    """测试 ArcticDB 并行读取"""
    print(f"\n[ArcticDB] 并行读取测试 ({workers} 线程)")
    
    from data_svc.storage.arcticdb_manager import ArcticDBManager
    
    manager = ArcticDBManager()
    lib = manager._get_or_create_library("daily")
    
    symbols = lib.list_symbols()
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    
    t0 = time.perf_counter()
    
    def read_symbol(sym):
        try:
            result = lib.read(sym)
            data = result.data
            if hasattr(data, '__arrow_c_array__'):
                df = pl.from_arrow(data)
            else:
                df = pl.from_pandas(data)
            return df if not df.is_empty() else None
        except Exception:
            return None
    
    all_dfs = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(read_symbol, sym): sym for sym in symbols}
        for future in as_completed(futures):
            df = future.result()
            if df is not None:
                all_dfs.append(df)
    
    elapsed = time.perf_counter() - t0
    total_rows = sum(len(df) for df in all_dfs)
    print(f"[ArcticDB-并行] 完成: {len(all_dfs)} 只股票, {total_rows:,} 行, 耗时 {elapsed:.2f}s")
    
    return elapsed, total_rows


def test_parquet_read(parquet_path: Path):
    """测试 Parquet 直接读取"""
    print("\n" + "-" * 70)
    print("[Parquet] Polars 直接读取测试")
    print("-" * 70)
    
    if not parquet_path.exists():
        print(f"[Parquet] 文件不存在: {parquet_path}")
        return None, 0
    
    file_size = parquet_path.stat().st_size / (1024 * 1024)
    print(f"文件: {parquet_path.name}")
    print(f"大小: {file_size:.1f} MB")
    
    t0 = time.perf_counter()
    df = pl.read_parquet(parquet_path)
    elapsed = time.perf_counter() - t0
    
    print(f"[Parquet] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[Parquet] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    return elapsed, len(df)


def test_duckdb_read(parquet_path: Path):
    """测试 DuckDB 读取"""
    print("\n" + "-" * 70)
    print("[DuckDB] 读取测试")
    print("-" * 70)
    
    import duckdb
    
    if not parquet_path.exists():
        print(f"[DuckDB] 文件不存在: {parquet_path}")
        return None, 0
    
    file_size = parquet_path.stat().st_size / (1024 * 1024)
    print(f"文件: {parquet_path.name}")
    print(f"大小: {file_size:.1f} MB")
    
    t0 = time.perf_counter()
    
    conn = duckdb.connect()
    result = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()
    total_rows = result[0] if result else 0
    
    elapsed = time.perf_counter() - t0
    print(f"[DuckDB] 完成: {total_rows:,} 行, 耗时 {elapsed:.2f}s")
    print(f"[DuckDB] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    conn.close()
    return elapsed, total_rows


def test_duckdb_arrow_read(parquet_path: Path):
    """测试 DuckDB + Arrow 零拷贝读取"""
    print("\n[DuckDB] Arrow 零拷贝读取测试")
    
    import duckdb
    
    if not parquet_path.exists():
        print(f"[DuckDB] 文件不存在: {parquet_path}")
        return None, 0
    
    file_size = parquet_path.stat().st_size / (1024 * 1024)
    
    t0 = time.perf_counter()
    
    conn = duckdb.connect()
    result = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}')").fetch_arrow_table()
    df = pl.from_arrow(result)
    
    elapsed = time.perf_counter() - t0
    print(f"[DuckDB-Arrow] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[DuckDB-Arrow] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    conn.close()
    return elapsed, len(df)


def test_parquet_lazy_read(parquet_path: Path):
    """测试 Parquet 懒加载读取"""
    print("\n[Parquet] 懒加载读取测试")
    
    if not parquet_path.exists():
        print(f"[Parquet] 文件不存在: {parquet_path}")
        return None, 0
    
    file_size = parquet_path.stat().st_size / (1024 * 1024)
    
    t0 = time.perf_counter()
    
    lf = pl.scan_parquet(parquet_path)
    df = lf.collect()
    
    elapsed = time.perf_counter() - t0
    print(f"[Parquet-Lazy] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[Parquet-Lazy] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    return elapsed, len(df)


def test_parquet_filtered_read(parquet_path: Path):
    """测试 Parquet 过滤读取"""
    print("\n[Parquet] 过滤读取测试 (按日期范围)")
    
    if not parquet_path.exists():
        print(f"[Parquet] 文件不存在: {parquet_path}")
        return None, 0
    
    t0 = time.perf_counter()
    
    lf = pl.scan_parquet(parquet_path)
    df = lf.filter(
        (pl.col("trade_date") >= "2024-01-01") & 
        (pl.col("trade_date") <= "2024-12-31")
    ).collect()
    
    elapsed = time.perf_counter() - t0
    print(f"[Parquet-Filtered] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    
    return elapsed, len(df)


def main():
    print("\n开始性能测试...\n")
    
    test_limit = 1000
    parquet_path = Path(__file__).parent.parent / "data" / "parquet_benchmark" / "daily_all.parquet"
    
    if not parquet_path.exists():
        print("Parquet 文件不存在，开始导出...")
        parquet_path, _ = export_to_parquet(limit=test_limit)
        if not parquet_path:
            print("导出失败，退出测试")
            return
    
    results = {}
    
    arctic_time, arctic_rows = test_arcticdb_serial(symbols_limit=test_limit)
    results['ArcticDB-串行'] = arctic_time
    
    arctic_p_time, _ = test_arcticdb_parallel(symbols_limit=test_limit, workers=5)
    results['ArcticDB-并行'] = arctic_p_time
    
    parquet_time, _ = test_parquet_read(parquet_path)
    if parquet_time:
        results['Parquet'] = parquet_time
    
    duckdb_time, _ = test_duckdb_read(parquet_path)
    if duckdb_time:
        results['DuckDB'] = duckdb_time
    
    duckdb_arrow_time, _ = test_duckdb_arrow_read(parquet_path)
    if duckdb_arrow_time:
        results['DuckDB-Arrow'] = duckdb_arrow_time
    
    parquet_lazy_time, _ = test_parquet_lazy_read(parquet_path)
    if parquet_lazy_time:
        results['Parquet-Lazy'] = parquet_lazy_time
    
    parquet_filtered_time, _ = test_parquet_filtered_read(parquet_path)
    if parquet_filtered_time:
        results['Parquet-Filtered'] = parquet_filtered_time
    
    print("\n" + "=" * 70)
    print("性能对比汇总")
    print("=" * 70)
    print(f"{'存储方式':<20} {'耗时':<15} {'相对速度':<10}")
    print("-" * 70)
    
    baseline = results.get('ArcticDB-串行', 1)
    for name, elapsed in sorted(results.items(), key=lambda x: x[1] if x[1] else float('inf')):
        if elapsed:
            speedup = baseline / elapsed
            print(f"{name:<20} {elapsed:>10.2f}s    {speedup:>6.2f}x")
    
    print("=" * 70)
    
    fastest = min((k for k, v in results.items() if v), key=lambda k: results[k])
    fastest_speedup = baseline / results[fastest]
    
    print(f"\n结论:")
    print(f"1. 最快方式: {fastest} ({fastest_speedup:.1f}x 加速)")
    print(f"2. ArcticDB 适合: 写入频繁、版本管理需求")
    print(f"3. Parquet/DuckDB 适合: 批量读取、分析查询")
    print(f"4. 建议: 使用 Parquet 作为缓存层，启动时预加载到内存")


if __name__ == "__main__":
    main()
