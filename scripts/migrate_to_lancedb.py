"""
数据迁移脚本: Parquet -> LanceDB
================================

将现有 Parquet 数据迁移到 LanceDB。

使用方式:
    python scripts/migrate_to_lancedb.py [--source SOURCE] [--target TARGET]
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from loguru import logger

from data_svc.storage.lancedb_manager import LanceDBManager, get_lancedb_manager


def migrate_from_parquet(
    source_path: str,
    target_path: Optional[str] = None,
    batch_size: int = 1_000_000,
    create_index: bool = True,
) -> dict:
    """
    从 Parquet 迁移数据到 LanceDB
    
    Args:
        source_path: Parquet 文件路径
        target_path: LanceDB 目标路径
        batch_size: 批量写入大小
        create_index: 是否创建索引
        
    Returns:
        迁移统计信息
    """
    logger.info("=" * 70)
    logger.info("Parquet -> LanceDB 数据迁移")
    logger.info("=" * 70)
    
    source = Path(source_path)
    if not source.exists():
        logger.error(f"源文件不存在: {source}")
        return {"success": False, "error": "源文件不存在"}
    
    file_size_mb = source.stat().st_size / (1024 * 1024)
    logger.info(f"源文件: {source}")
    logger.info(f"文件大小: {file_size_mb:.1f} MB")
    
    t_start = time.perf_counter()
    
    logger.info("\n[步骤 1/4] 读取 Parquet 数据...")
    t0 = time.perf_counter()
    df = pl.read_parquet(source)
    read_time = time.perf_counter() - t0
    logger.info(f"  读取完成: {len(df):,} 行, {df.width} 列, 耗时 {read_time:.2f}s")
    
    logger.info("\n[步骤 2/4] 规范化数据格式...")
    t0 = time.perf_counter()
    
    if "trade_date" in df.columns:
        dtype = df.schema["trade_date"]
        if dtype == pl.Date:
            pass
        elif dtype == pl.Datetime:
            df = df.with_columns(
                pl.col("trade_date").dt.date()
            )
        else:
            df = df.with_columns(
                pl.col("trade_date").str.to_date()
            )
    
    float_cols = ["open", "high", "low", "close", "volume", "amount",
                  "change_pct", "turnover_rate", "total_mv", "float_mv",
                  "prev_close", "change_amount", "turnover_free", "volume_ratio",
                  "pe", "pe_ttm", "pb", "ps", "ps_ttm", "dividend_yield",
                  "dividend_yield_ttm", "total_shares", "float_shares",
                  "free_float_shares", "limit_up", "limit_down", "adj_factor"]
    for col in float_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Float64))
    
    norm_time = time.perf_counter() - t0
    logger.info(f"  规范化完成: 耗时 {norm_time:.2f}s")
    
    logger.info("\n[步骤 3/4] 写入 LanceDB...")
    t0 = time.perf_counter()
    
    manager = LanceDBManager(target_path)
    
    total_rows = len(df)
    if total_rows <= batch_size:
        rows_written = manager.write_daily_data(df, mode="overwrite")
    else:
        rows_written = 0
        for i in range(0, total_rows, batch_size):
            batch = df.slice(i, batch_size)
            if i == 0:
                rows = manager.write_daily_data(batch, mode="overwrite")
            else:
                rows = manager.write_daily_data(batch, mode="append")
            rows_written += rows
            logger.info(f"  进度: {min(i + batch_size, total_rows):,}/{total_rows:,} 行")
    
    write_time = time.perf_counter() - t0
    logger.info(f"  写入完成: {rows_written:,} 行, 耗时 {write_time:.2f}s")
    
    if create_index:
        logger.info("\n[步骤 4/4] 创建索引...")
        t0 = time.perf_counter()
        try:
            manager.table.create_scalar_index("trade_date", replace=True)
            index_time = time.perf_counter() - t0
            logger.info(f"  索引创建完成: 耗时 {index_time:.2f}s")
        except Exception as e:
            logger.warning(f"  索引创建失败: {e}")
            index_time = 0
    else:
        index_time = 0
    
    total_time = time.perf_counter() - t_start
    
    stats = manager.get_stats()
    
    logger.info("\n" + "=" * 70)
    logger.info("迁移完成")
    logger.info("=" * 70)
    logger.info(f"总行数: {rows_written:,}")
    logger.info(f"读取耗时: {read_time:.2f}s")
    logger.info(f"写入耗时: {write_time:.2f}s")
    logger.info(f"索引耗时: {index_time:.2f}s")
    logger.info(f"总耗时: {total_time:.2f}s")
    logger.info(f"吞吐量: {file_size_mb / total_time:.1f} MB/s")
    logger.info(f"目标路径: {manager.db_path}")
    
    return {
        "success": True,
        "rows_written": rows_written,
        "read_time": read_time,
        "write_time": write_time,
        "index_time": index_time,
        "total_time": total_time,
        "throughput_mbps": file_size_mb / total_time,
        "target_path": str(manager.db_path),
    }


def verify_migration(
    source_path: str,
    target_path: Optional[str] = None,
) -> bool:
    """
    验证迁移结果
    
    Args:
        source_path: Parquet 文件路径
        target_path: LanceDB 目标路径
        
    Returns:
        是否验证通过
    """
    logger.info("\n" + "=" * 70)
    logger.info("验证迁移结果")
    logger.info("=" * 70)
    
    source = Path(source_path)
    
    logger.info("\n[验证 1] 行数对比...")
    df_parquet = pl.read_parquet(source)
    parquet_rows = len(df_parquet)
    logger.info(f"  Parquet 行数: {parquet_rows:,}")
    
    manager = LanceDBManager(target_path)
    lancedb_rows = manager.table.count_rows() if manager.table else 0
    logger.info(f"  LanceDB 行数: {lancedb_rows:,}")
    
    if parquet_rows != lancedb_rows:
        logger.error(f"  ❌ 行数不匹配!")
        return False
    logger.info(f"  ✅ 行数匹配")
    
    logger.info("\n[验证 2] 数据抽样对比...")
    sample_date = df_parquet.select("trade_date").unique().head(1)["trade_date"][0]
    sample_date = str(sample_date)
    
    from data_svc.storage.lancedb_reader import LanceDBDataReader
    reader = LanceDBDataReader(target_path)
    
    df_lance = reader.read_all(sample_date, sample_date)
    
    parquet_sample = df_parquet.filter(pl.col("trade_date") == sample_date)
    lance_sample = df_lance.filter(pl.col("trade_date") == sample_date)
    
    if len(parquet_sample) != len(lance_sample):
        logger.error(f"  ❌ 抽样数据行数不匹配!")
        return False
    logger.info(f"  ✅ 抽样数据匹配 ({sample_date}: {len(parquet_sample)} 行)")
    
    logger.info("\n[验证 3] 查询性能测试...")
    t0 = time.perf_counter()
    df_test = reader.read_all("2024-01-01", "2024-12-31")
    query_time = time.perf_counter() - t0
    logger.info(f"  查询 2024 年数据: {len(df_test):,} 行, {query_time:.2f}s")
    
    if query_time < 5:
        logger.info(f"  ✅ 查询性能达标 (< 5s)")
    else:
        logger.warning(f"  ⚠️ 查询性能较慢 (> 5s)")
    
    logger.info("\n" + "=" * 70)
    logger.info("验证完成: 全部通过 ✅")
    logger.info("=" * 70)
    
    return True


def benchmark_comparison(
    source_path: str,
    target_path: Optional[str] = None,
) -> dict:
    """
    性能对比测试
    
    Args:
        source_path: Parquet 文件路径
        target_path: LanceDB 目标路径
        
    Returns:
        性能对比结果
    """
    logger.info("\n" + "=" * 70)
    logger.info("性能对比测试")
    logger.info("=" * 70)
    
    results = {}
    
    logger.info("\n[测试 1] 全量读取...")
    
    t0 = time.perf_counter()
    df_pq = pl.read_parquet(source_path)
    t_parquet = time.perf_counter() - t0
    logger.info(f"  Parquet: {t_parquet:.2f}s")
    
    from data_svc.storage.lancedb_reader import LanceDBDataReader
    reader = LanceDBDataReader(target_path)
    reader.clear_cache()
    
    t0 = time.perf_counter()
    df_lance = reader.read_all()
    t_lance = time.perf_counter() - t0
    logger.info(f"  LanceDB: {t_lance:.2f}s")
    
    results["full_read"] = {
        "parquet": t_parquet,
        "lancedb": t_lance,
        "ratio": t_lance / t_parquet,
    }
    
    logger.info("\n[测试 2] 日期范围查询 (2024-01-01 ~ 2024-12-31)...")
    
    t0 = time.perf_counter()
    df_pq_filtered = df_pq.filter(
        (pl.col("trade_date") >= "2024-01-01") &
        (pl.col("trade_date") <= "2024-12-31")
    )
    t_parquet_filtered = time.perf_counter() - t0
    logger.info(f"  Parquet (内存过滤): {t_parquet_filtered:.2f}s")
    
    reader.clear_cache()
    t0 = time.perf_counter()
    df_lance_filtered = reader.read_all("2024-01-01", "2024-12-31")
    t_lance_filtered = time.perf_counter() - t0
    logger.info(f"  LanceDB (索引查询): {t_lance_filtered:.2f}s")
    
    results["date_range_query"] = {
        "parquet": t_parquet_filtered,
        "lancedb": t_lance_filtered,
        "ratio": t_lance_filtered / t_parquet_filtered if t_parquet_filtered > 0 else 0,
    }
    
    logger.info("\n[测试 3] 单日查询...")
    
    sample_date = "2024-01-02"
    
    t0 = time.perf_counter()
    df_pq_day = df_pq.filter(pl.col("trade_date") == sample_date)
    t_parquet_day = time.perf_counter() - t0
    logger.info(f"  Parquet: {t_parquet_day:.3f}s")
    
    reader.clear_cache()
    t0 = time.perf_counter()
    df_lance_day = reader.read_all(sample_date, sample_date)
    t_lance_day = time.perf_counter() - t0
    logger.info(f"  LanceDB: {t_lance_day:.3f}s")
    
    results["single_day_query"] = {
        "parquet": t_parquet_day,
        "lancedb": t_lance_day,
        "ratio": t_lance_day / t_parquet_day if t_parquet_day > 0 else 0,
    }
    
    logger.info("\n" + "=" * 70)
    logger.info("性能对比汇总")
    logger.info("=" * 70)
    logger.info(f"{'测试项':<25} {'Parquet':<12} {'LanceDB':<12} {'比值':<10}")
    logger.info("-" * 60)
    for name, data in results.items():
        logger.info(
            f"{name:<25} {data['parquet']:>8.2f}s   {data['lancedb']:>8.2f}s   {data['ratio']:>6.2f}x"
        )
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Parquet -> LanceDB 数据迁移")
    parser.add_argument(
        "--source",
        type=str,
        default="data/parquet_data/stock_daily.parquet",
        help="Parquet 源文件路径",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="LanceDB 目标路径",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1_000_000,
        help="批量写入大小",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="不创建索引",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="迁移后验证",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="性能对比测试",
    )
    
    args = parser.parse_args()
    
    source_path = Path(project_root) / args.source
    
    result = migrate_from_parquet(
        source_path=str(source_path),
        target_path=args.target,
        batch_size=args.batch_size,
        create_index=not args.no_index,
    )
    
    if not result["success"]:
        return 1
    
    if args.verify:
        if not verify_migration(str(source_path), args.target):
            return 1
    
    if args.benchmark:
        benchmark_comparison(str(source_path), args.target)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
