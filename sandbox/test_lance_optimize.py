"""
LanceDB 性能优化测试

尝试各种方法让 LanceDB 达到 Parquet 的读取速度
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import shutil
import polars as pl

print("=" * 70)
print("LanceDB 性能优化测试")
print("=" * 70)

PARQUET_PATH = Path(__file__).parent.parent / "data" / "parquet_data" / "stock_daily.parquet"
LANCE_DIR = Path(__file__).parent.parent / "data" / "test_lancedb_optimized"


def test_parquet_baseline():
    """Parquet 基准测试"""
    print("\n[Parquet] 基准测试...")
    t0 = time.perf_counter()
    df = pl.read_parquet(PARQUET_PATH)
    t = time.perf_counter() - t0
    print(f"  耗时: {t:.2f}s, 行数: {len(df):,}")
    return t


def test_lance_v1():
    """LanceDB v1: 默认参数创建"""
    print("\n[LanceDB v1] 默认参数创建...")
    
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True)
    
    df = pl.read_parquet(PARQUET_PATH)
    
    import lancedb
    db = lancedb.connect(str(LANCE_DIR))
    
    t0 = time.perf_counter()
    table = db.create_table("stock_daily", df.to_arrow())
    create_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result = table.to_arrow()
    read_time = time.perf_counter() - t0
    
    print(f"  创建: {create_time:.2f}s, 读取: {read_time:.2f}s")
    return read_time


def test_lance_v2():
    """LanceDB v2: 使用 write_options 优化"""
    print("\n[LanceDB v2] 使用优化参数创建...")
    
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True)
    
    df = pl.read_parquet(PARQUET_PATH)
    
    import lancedb
    db = lancedb.connect(str(LANCE_DIR))
    
    t0 = time.perf_counter()
    
    # 使用 LanceWriteOptions 优化
    table = db.create_table(
        "stock_daily",
        df.to_arrow(),
        mode="overwrite"
    )
    
    create_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result = table.to_arrow()
    read_time = time.perf_counter() - t0
    
    print(f"  创建: {create_time:.2f}s, 读取: {read_time:.2f}s")
    return read_time


def test_lance_v3():
    """LanceDB v3: 分批写入"""
    print("\n[LanceDB v3] 分批写入...")
    
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True)
    
    df = pl.read_parquet(PARQUET_PATH)
    
    import lancedb
    db = lancedb.connect(str(LANCE_DIR))
    
    t0 = time.perf_counter()
    
    # 先创建空表
    table = db.create_table("stock_daily", df.head(0).to_arrow())
    
    # 分批写入，每批 100 万行
    batch_size = 1_000_000
    for i in range(0, len(df), batch_size):
        batch = df.slice(i, batch_size)
        table.add(batch.to_arrow())
    
    create_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result = table.to_arrow()
    read_time = time.perf_counter() - t0
    
    print(f"  创建: {create_time:.2f}s, 读取: {read_time:.2f}s")
    return read_time


def test_lance_v4():
    """LanceDB v4: 使用 data_type 指定 schema"""
    print("\n[LanceDB v4] 指定 schema...")
    
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True)
    
    df = pl.read_parquet(PARQUET_PATH)
    
    import lancedb
    from lancedb import LanceWriteOptions
    
    db = lancedb.connect(str(LANCE_DIR))
    
    t0 = time.perf_counter()
    
    # 使用写入选项
    options = LanceWriteOptions(
        mode="overwrite"
    )
    
    table = db.create_table(
        "stock_daily",
        df.to_arrow(),
    )
    
    create_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result = table.to_arrow()
    read_time = time.perf_counter() - t0
    
    print(f"  创建: {create_time:.2f}s, 读取: {read_time:.2f}s")
    return read_time


def test_lance_v5():
    """LanceDB v5: 只保留必要列"""
    print("\n[LanceDB v5] 只保留必要列 (OHLCV)...")
    
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True)
    
    df = pl.read_parquet(PARQUET_PATH)
    
    # 只保留 OHLCV
    df_minimal = df.select([
        "stock_code", "trade_date", 
        "open", "high", "low", "close", "volume"
    ])
    
    import lancedb
    db = lancedb.connect(str(LANCE_DIR))
    
    t0 = time.perf_counter()
    table = db.create_table("stock_daily", df_minimal.to_arrow())
    create_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result = table.to_arrow()
    read_time = time.perf_counter() - t0
    
    print(f"  创建: {create_time:.2f}s, 读取: {read_time:.2f}s")
    return read_time


def test_lance_v6():
    """LanceDB v6: 使用 io_config 优化"""
    print("\n[LanceDB v6] 检查最新版本...")
    import lancedb
    print(f"  版本: {lancedb.__version__}")
    
    # 尝试不同的读取参数
    db = lancedb.connect(str(LANCE_DIR))
    table = db.open_table("stock_daily")
    
    t0 = time.perf_counter()
    
    # 尝试使用 limit 读取全部
    result = table.to_arrow()
    
    read_time = time.perf_counter() - t0
    print(f"  读取: {read_time:.2f}s")
    return read_time


def main():
    parquet_time = test_parquet_baseline()
    
    results = {"Parquet": parquet_time}
    
    results["Lance-v1"] = test_lance_v1()
    results["Lance-v2"] = test_lance_v2()
    results["Lance-v3"] = test_lance_v3()
    results["Lance-v5"] = test_lance_v5()
    results["Lance-v6"] = test_lance_v6()
    
    print("\n" + "=" * 70)
    print("性能对比汇总")
    print("=" * 70)
    print(f"{'方式':<20} {'耗时':<10} {'相对 Parquet':<15}")
    print("-" * 45)
    
    for name, t in sorted(results.items(), key=lambda x: x[1]):
        ratio = t / parquet_time
        print(f"{name:<20} {t:>8.2f}s   {ratio:>8.1f}x")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    best_lance = min((k, v) for k, v in results.items() if k != "Parquet")
    speedup = best_lance[1] / parquet_time
    
    if speedup < 2:
        print(f"✅ LanceDB 接近 Parquet: 仅慢 {speedup:.1f}x")
    else:
        print(f"❌ LanceDB 比 Parquet 慢 {speedup:.1f}x")
        print(f"   原因: LanceDB 设计目标不是批量分析")
        print(f"   优势: 向量检索、增量写入")


if __name__ == "__main__":
    main()
