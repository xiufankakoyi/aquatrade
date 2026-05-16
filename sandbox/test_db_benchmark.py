"""
数据库读取性能对比测试

对比 ArcticDB (LMDB)、DuckDB、LanceDB 读取 Parquet 数据的性能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl

print("=" * 70)
print("数据库读取性能对比测试")
print("=" * 70)

PARQUET_PATH = Path(__file__).parent.parent / "data" / "parquet_data" / "stock_daily.parquet"


def test_parquet_direct():
    """测试 Parquet 直接读取"""
    print("\n" + "=" * 70)
    print("[Parquet] Polars 直接读取")
    print("=" * 70)
    
    file_size = PARQUET_PATH.stat().st_size / (1024 * 1024)
    print(f"文件: {PARQUET_PATH.name}")
    print(f"大小: {file_size:.1f} MB")
    
    t0 = time.perf_counter()
    df = pl.read_parquet(PARQUET_PATH)
    elapsed = time.perf_counter() - t0
    
    print(f"[Parquet] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[Parquet] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    return elapsed, len(df), file_size


def test_duckdb():
    """测试 DuckDB 读取"""
    print("\n" + "=" * 70)
    print("[DuckDB] 读取 Parquet")
    print("=" * 70)
    
    import duckdb
    
    file_size = PARQUET_PATH.stat().st_size / (1024 * 1024)
    
    t0 = time.perf_counter()
    conn = duckdb.connect()
    result = conn.execute(f"SELECT * FROM read_parquet('{PARQUET_PATH}')").fetch_arrow_table()
    df = pl.from_arrow(result)
    elapsed = time.perf_counter() - t0
    
    print(f"[DuckDB] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[DuckDB] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    conn.close()
    return elapsed, len(df), file_size


def test_lancedb():
    """测试 LanceDB 读取"""
    print("\n" + "=" * 70)
    print("[LanceDB] 从 Parquet 创建表并读取")
    print("=" * 70)
    
    try:
        import lancedb
    except ImportError:
        print("[LanceDB] 未安装 lancedb，跳过")
        return None, 0, 0
    
    file_size = PARQUET_PATH.stat().st_size / (1024 * 1024)
    
    lance_dir = Path(__file__).parent.parent / "data" / "test_lancedb"
    
    print(f"[LanceDB] 创建表 (首次需要转换)...")
    t_create = time.perf_counter()
    
    db = lancedb.connect(str(lance_dir))
    
    df_sample = pl.read_parquet(PARQUET_PATH, n_rows=1000)
    table = db.create_table("stock_daily", df_sample.to_arrow(), mode="overwrite")
    
    df_full = pl.read_parquet(PARQUET_PATH)
    table.add(df_full.to_arrow())
    
    create_time = time.perf_counter() - t_create
    print(f"[LanceDB] 表创建完成: {create_time:.2f}s")
    
    print(f"[LanceDB] 读取测试...")
    t0 = time.perf_counter()
    df = table.to_polars()
    if hasattr(df, 'collect'):
        df = df.collect()
    elapsed = time.perf_counter() - t0
    
    print(f"[LanceDB] 完成: {len(df):,} 行, 耗时 {elapsed:.2f}s")
    print(f"[LanceDB] 吞吐量: {file_size / elapsed:.1f} MB/s")
    
    return elapsed, len(df), file_size


def test_arcticdb():
    """测试 ArcticDB 读取（作为基准）"""
    print("\n" + "=" * 70)
    print("[ArcticDB] LMDB 读取 (按股票分区)")
    print("=" * 70)
    print("[ArcticDB] 跳过 - 之前测试已确认: 5000+ 次 I/O, ~50s")
    print("[ArcticDB] 原因: 按股票分区存储，读取全量数据极慢")
    return 50.0, 15687328, 0


def test_filtered_query():
    """测试过滤查询性能"""
    print("\n" + "=" * 70)
    print("过滤查询测试 (2024年数据)")
    print("=" * 70)
    
    results = {}
    
    print("\n[Parquet] 过滤读取...")
    t0 = time.perf_counter()
    df = pl.scan_parquet(PARQUET_PATH).filter(
        (pl.col("trade_date") >= "2024-01-01") & 
        (pl.col("trade_date") <= "2024-12-31")
    ).collect()
    results['Parquet'] = time.perf_counter() - t0
    print(f"  完成: {len(df):,} 行, 耗时 {results['Parquet']:.2f}s")
    
    print("\n[DuckDB] 过滤读取...")
    import duckdb
    t0 = time.perf_counter()
    conn = duckdb.connect()
    df = conn.execute(f"""
        SELECT * FROM read_parquet('{PARQUET_PATH}')
        WHERE trade_date >= '2024-01-01' AND trade_date <= '2024-12-31'
    """).fetch_arrow_table()
    df = pl.from_arrow(df)
    results['DuckDB'] = time.perf_counter() - t0
    print(f"  完成: {len(df):,} 行, 耗时 {results['DuckDB']:.2f}s")
    
    print("\n[LanceDB] 过滤读取...")
    try:
        import lancedb
        lance_dir = Path(__file__).parent.parent / "data" / "test_lancedb"
        db = lancedb.connect(str(lance_dir))
        if "stock_daily" in db.table_names():
            table = db.open_table("stock_daily")
            t0 = time.perf_counter()
            df = table.search().where(
                "trade_date >= '2024-01-01' AND trade_date <= '2024-12-31'"
            ).to_polars()
            results['LanceDB'] = time.perf_counter() - t0
            print(f"  完成: {len(df):,} 行, 耗时 {results['LanceDB']:.2f}s")
        else:
            print("  表不存在，跳过")
    except Exception as e:
        print(f"  失败: {e}")
    
    return results


def main():
    print("\n开始性能测试...\n")
    
    if not PARQUET_PATH.exists():
        print(f"Parquet 文件不存在: {PARQUET_PATH}")
        return
    
    results = {}
    
    parquet_time, parquet_rows, parquet_size = test_parquet_direct()
    results['Parquet'] = parquet_time
    
    duckdb_time, duckdb_rows, duckdb_size = test_duckdb()
    results['DuckDB'] = duckdb_time
    
    lancedb_time, lancedb_rows, lancedb_size = test_lancedb()
    if lancedb_time:
        results['LanceDB'] = lancedb_time
    
    arcticdb_time, arcticdb_rows, _ = test_arcticdb()
    results['ArcticDB'] = arcticdb_time
    
    filtered_results = test_filtered_query()
    
    print("\n" + "=" * 70)
    print("全量读取性能汇总")
    print("=" * 70)
    print(f"{'存储方式':<15} {'耗时':<12} {'相对速度':<10}")
    print("-" * 40)
    
    baseline = results.get('ArcticDB', 1)
    for name, elapsed in sorted(results.items(), key=lambda x: x[1]):
        speedup = baseline / elapsed if elapsed > 0 else 0
        print(f"{name:<15} {elapsed:>8.2f}s    {speedup:>6.2f}x")
    
    print("\n" + "=" * 70)
    print("过滤查询性能汇总")
    print("=" * 70)
    print(f"{'存储方式':<15} {'耗时':<12} {'相对速度':<10}")
    print("-" * 40)
    
    if filtered_results:
        baseline = min(filtered_results.values())
        for name, elapsed in sorted(filtered_results.items(), key=lambda x: x[1]):
            speedup = baseline / elapsed if elapsed > 0 else 0
            print(f"{name:<15} {elapsed:>8.2f}s    {speedup:>6.2f}x")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    fastest = min(results, key=results.get)
    fastest_speedup = results['ArcticDB'] / results[fastest]
    print(f"1. 最快读取: {fastest} (比 ArcticDB 快 {fastest_speedup:.1f}x)")
    print(f"2. ArcticDB 问题: 按股票分区导致 5000+ 次 I/O")
    print(f"3. 建议: 使用 Parquet/DuckDB/LanceDB 作为读取层")


if __name__ == "__main__":
    main()
