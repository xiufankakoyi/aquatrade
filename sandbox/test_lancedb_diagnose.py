"""
LanceDB 性能诊断测试

分析 LanceDB 读取慢的原因
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl

print("=" * 70)
print("LanceDB 性能诊断测试")
print("=" * 70)

PARQUET_PATH = Path(__file__).parent.parent / "data" / "parquet_data" / "stock_daily.parquet"
LANCE_DIR = Path(__file__).parent.parent / "data" / "test_lancedb"


def diagnose_lancedb():
    import lancedb
    
    print("\n[诊断 1] 检查表结构...")
    db = lancedb.connect(str(LANCE_DIR))
    print(f"表列表: {db.table_names()}")
    
    table = db.open_table("stock_daily")
    print(f"表行数: {table.count_rows()}")
    
    schema = table.schema
    print(f"Schema: {schema}")
    
    print("\n[诊断 2] 测试不同读取方式...")
    
    print("\n方式 1: to_polars() (当前方式)")
    t0 = time.perf_counter()
    df = table.to_polars()
    if hasattr(df, 'collect'):
        df = df.collect()
    t1 = time.perf_counter() - t0
    print(f"  耗时: {t1:.2f}s, 行数: {len(df)}")
    
    print("\n方式 2: to_pandas() 转换")
    t0 = time.perf_counter()
    df_pd = table.to_pandas()
    t2 = time.perf_counter() - t0
    print(f"  耗时: {t2:.2f}s, 行数: {len(df_pd)}")
    
    print("\n方式 3: to_arrow() 直接读取")
    t0 = time.perf_counter()
    arrow_table = table.to_arrow()
    df_arrow = pl.from_arrow(arrow_table)
    t3 = time.perf_counter() - t0
    print(f"  耗时: {t3:.2f}s, 行数: {len(df_arrow)}")
    
    print("\n方式 4: search().to_polars() 空查询")
    t0 = time.perf_counter()
    df_search = table.search().to_polars()
    if hasattr(df_search, 'collect'):
        df_search = df_search.collect()
    t4 = time.perf_counter() - t0
    print(f"  耗时: {t4:.2f}s, 行数: {len(df_search)}")
    
    print("\n方式 5: 检查 LanceDB 版本和配置")
    import lancedb
    print(f"  LanceDB 版本: {lancedb.__version__}")
    
    print("\n[诊断 3] 检查是否使用了索引...")
    try:
        index_stats = table.index_stats()
        print(f"索引统计: {index_stats}")
    except Exception as e:
        print(f"无索引: {e}")
    
    print("\n[诊断 4] 检查文件大小...")
    lance_files = list(LANCE_DIR.glob("**/*.lance"))
    total_size = sum(f.stat().st_size for f in lance_files if f.is_file()) / (1024*1024)
    print(f"LanceDB 文件总大小: {total_size:.1f} MB")
    print(f"Parquet 文件大小: {PARQUET_PATH.stat().st_size / (1024*1024):.1f} MB")
    
    print("\n" + "=" * 70)
    print("读取方式对比汇总")
    print("=" * 70)
    print(f"{'方式':<35} {'耗时':<10}")
    print("-" * 45)
    print(f"{'to_polars()':<35} {t1:>8.2f}s")
    print(f"{'to_pandas()':<35} {t2:>8.2f}s")
    print(f"{'to_arrow()':<35} {t3:>8.2f}s")
    print(f"{'search().to_polars()':<35} {t4:>8.2f}s")
    
    print("\n[Parquet 基准]")
    t0 = time.perf_counter()
    df_pq = pl.read_parquet(PARQUET_PATH)
    t_pq = time.perf_counter() - t0
    print(f"Polars read_parquet: {t_pq:.2f}s")


if __name__ == "__main__":
    diagnose_lancedb()
