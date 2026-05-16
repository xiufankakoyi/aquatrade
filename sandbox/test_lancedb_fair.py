"""
LanceDB vs Parquet 公平对比测试

确保数据量相同，对比真实性能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import shutil
import polars as pl

print("=" * 70)
print("LanceDB vs Parquet 公平对比测试")
print("=" * 70)

PARQUET_PATH = Path(__file__).parent.parent / "data" / "parquet_data" / "stock_daily.parquet"
LANCE_DIR = Path(__file__).parent.parent / "data" / "test_lancedb_clean"


def main():
    print("\n[步骤 1] 读取 Parquet 数据...")
    t0 = time.perf_counter()
    df = pl.read_parquet(PARQUET_PATH)
    print(f"  数据量: {len(df):,} 行, {df.width} 列")
    print(f"  读取耗时: {time.perf_counter() - t0:.2f}s")
    
    print("\n[步骤 2] 清理旧 LanceDB 数据...")
    if LANCE_DIR.exists():
        shutil.rmtree(LANCE_DIR)
    LANCE_DIR.mkdir(parents=True, exist_ok=True)
    
    print("\n[步骤 3] 创建 LanceDB 表...")
    import lancedb
    
    t0 = time.perf_counter()
    db = lancedb.connect(str(LANCE_DIR))
    table = db.create_table("stock_daily", df.to_arrow())
    create_time = time.perf_counter() - t0
    print(f"  创建耗时: {create_time:.2f}s")
    
    print("\n[步骤 4] 检查文件大小...")
    lance_size = sum(f.stat().st_size for f in LANCE_DIR.rglob("*") if f.is_file()) / (1024*1024)
    parquet_size = PARQUET_PATH.stat().st_size / (1024*1024)
    print(f"  Parquet: {parquet_size:.1f} MB")
    print(f"  LanceDB: {lance_size:.1f} MB")
    print(f"  压缩比: {lance_size/parquet_size:.2f}x")
    
    print("\n[步骤 5] 读取性能测试...")
    
    print("\n  [Parquet] 读取...")
    t0 = time.perf_counter()
    df_pq = pl.read_parquet(PARQUET_PATH)
    t_parquet = time.perf_counter() - t0
    print(f"    耗时: {t_parquet:.2f}s, 吞吐量: {parquet_size/t_parquet:.0f} MB/s")
    
    print("\n  [LanceDB] to_polars()...")
    t0 = time.perf_counter()
    df_lance = table.to_polars()
    if hasattr(df_lance, 'collect'):
        df_lance = df_lance.collect()
    t_lance = time.perf_counter() - t0
    print(f"    耗时: {t_lance:.2f}s, 吞吐量: {lance_size/t_lance:.0f} MB/s")
    
    print("\n  [LanceDB] to_arrow()...")
    t0 = time.perf_counter()
    arrow = table.to_arrow()
    df_arrow = pl.from_arrow(arrow)
    t_arrow = time.perf_counter() - t0
    print(f"    耗时: {t_arrow:.2f}s, 吞吐量: {lance_size/t_arrow:.0f} MB/s")
    
    print("\n  [LanceDB] to_pandas() -> Polars...")
    t0 = time.perf_counter()
    df_pd = pl.from_pandas(table.to_pandas())
    t_pd = time.perf_counter() - t0
    print(f"    耗时: {t_pd:.2f}s, 吞吐量: {lance_size/t_pd:.0f} MB/s")
    
    print("\n" + "=" * 70)
    print("性能对比汇总")
    print("=" * 70)
    print(f"{'方式':<30} {'耗时':<10} {'吞吐量':<15}")
    print("-" * 55)
    print(f"{'Parquet (Polars)':<30} {t_parquet:>6.2f}s   {parquet_size/t_parquet:>8.0f} MB/s")
    print(f"{'LanceDB to_polars()':<30} {t_lance:>6.2f}s   {lance_size/t_lance:>8.0f} MB/s")
    print(f"{'LanceDB to_arrow()':<30} {t_arrow:>6.2f}s   {lance_size/t_arrow:>8.0f} MB/s")
    print(f"{'LanceDB to_pandas()':<30} {t_pd:>6.2f}s   {lance_size/t_pd:>8.0f} MB/s")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    speedup = t_lance / t_parquet
    print(f"1. Parquet 比 LanceDB 快 {speedup:.1f}x")
    print(f"2. LanceDB 存储大小: {lance_size/parquet_size:.1f}x Parquet")
    print(f"3. LanceDB 优势: 支持向量检索、增量写入")
    print(f"4. Parquet 优势: 读取速度最快、压缩率高")


if __name__ == "__main__":
    main()
