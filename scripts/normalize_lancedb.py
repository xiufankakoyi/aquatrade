"""
LanceDB 数据规范化迁移脚本
===========================

解决问题:
1. 股票代码格式不一致 (000001 vs 000001.SZ)
2. 格式统一后去重
3. 数据缺口补全

使用方式:
    python scripts/normalize_lancedb.py [--dry-run]
"""

import sys
import time
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import pyarrow as pa
from loguru import logger

import lancedb


def normalize_stock_code(code: str) -> str:
    """
    将股票代码统一为带交易所后缀的格式

    规则:
    - 6开头 → .SH (上海)
    - 0/3开头 → .SZ (深圳)
    - 4/8开头 → .BJ (北京)
    - 已有后缀 → 不变
    - ETF/指数 5开头 → .SH
    """
    if code is None:
        return code

    code = str(code).strip()

    if '.' in code:
        return code

    if len(code) < 6:
        return code

    first_char = code[0]
    if first_char == '6':
        return f"{code}.SH"
    elif first_char in ('0', '3'):
        return f"{code}.SZ"
    elif first_char in ('4', '8', '9'):
        return f"{code}.BJ"
    elif first_char == '5':
        return f"{code}.SH"
    else:
        return code


def normalize_stock_code_polars(code_series: pl.Series) -> pl.Series:
    """批量规范化股票代码 (Polars 版本)"""
    codes = code_series.to_list()
    normalized = [normalize_stock_code(c) for c in codes]
    return pl.Series(name=code_series.name, values=normalized)


def normalize_table(
    db_path: str,
    table_name: str,
    code_column: str = "stock_code",
    dry_run: bool = False,
) -> dict:
    """
    规范化 LanceDB 表中的股票代码

    策略: 按日期分批读取 → 规范化代码 → 去重 → 写回

    Args:
        db_path: LanceDB 路径
        table_name: 表名
        code_column: 股票代码列名
        dry_run: 只分析不写入

    Returns:
        处理统计信息
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"规范化表: {table_name}")
    logger.info(f"{'='*70}")

    db = lancedb.connect(db_path)

    result = db.list_tables()
    existing_tables = result.tables if hasattr(result, 'tables') else list(result)
    if table_name not in existing_tables:
        logger.warning(f"表 {table_name} 不存在，跳过")
        return {"success": False, "error": "table not found"}

    table = db.open_table(table_name)
    ds = table.to_lance()

    total_rows_before = table.count_rows()
    logger.info(f"当前行数: {total_rows_before:,}")

    # 检查是否有需要规范化的代码
    scanner = ds.scanner(columns=[code_column])
    arrow_table = scanner.to_table()
    df_codes = pl.from_arrow(arrow_table)

    codes = df_codes[code_column].to_list()
    needs_normalize = sum(1 for c in codes if '.' not in str(c))
    already_normalized = sum(1 for c in codes if '.' in str(c))

    logger.info(f"需要规范化 (无后缀): {needs_normalize:,}")
    logger.info(f"已规范化 (有后缀): {already_normalized:,}")

    if needs_normalize == 0:
        logger.info("所有代码已规范化，无需处理")
        return {"success": True, "rows_affected": 0}

    if dry_run:
        logger.info("[DRY RUN] 仅分析，不写入")
        return {"success": True, "rows_affected": needs_normalize, "dry_run": True}

    t_start = time.perf_counter()

    # 读取全量数据
    logger.info("读取全量数据...")
    t0 = time.perf_counter()
    scanner = ds.scanner()
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)
    logger.info(f"读取完成: {len(df):,} 行, {time.perf_counter() - t0:.2f}s")

    # 规范化股票代码
    logger.info("规范化股票代码...")
    t0 = time.perf_counter()
    df = df.with_columns(
        normalize_stock_code_polars(df[code_column]).alias(code_column)
    )
    logger.info(f"规范化完成: {time.perf_counter() - t0:.2f}s")

    # 去重: 同一股票同一日期只保留一条记录
    # 优先保留有更多字段的记录 (有后缀版本通常更新)
    logger.info("去重...")
    t0 = time.perf_counter()

    dedup_cols = [code_column]
    if "trade_date" in df.columns:
        dedup_cols.append("trade_date")

    before_dedup = len(df)
    df = df.unique(subset=dedup_cols, keep="last")
    after_dedup = len(df)
    logger.info(f"去重: {before_dedup:,} → {after_dedup:,} (删除 {before_dedup - after_dedup:,} 条重复)")

    # 排序
    if "trade_date" in df.columns:
        df = df.sort([code_column, "trade_date"])

    # 删除旧表并重建
    logger.info("重建表...")
    t0 = time.perf_counter()

    db.drop_table(table_name)
    new_table = db.create_table(table_name, df.to_arrow())

    # 创建索引
    try:
        if "trade_date" in df.columns:
            new_table.create_scalar_index("trade_date", replace=True)
            logger.info("创建 trade_date 索引")
    except Exception as e:
        logger.warning(f"创建索引失败: {e}")

    logger.info(f"重建完成: {time.perf_counter() - t0:.2f}s")

    total_rows_after = new_table.count_rows()
    total_time = time.perf_counter() - t_start

    logger.info(f"\n结果: {total_rows_before:,} → {total_rows_after:,} 行, 耗时 {total_time:.2f}s")

    return {
        "success": True,
        "rows_before": total_rows_before,
        "rows_after": total_rows_after,
        "rows_normalized": needs_normalize,
        "rows_deduplicated": before_dedup - after_dedup,
        "time_seconds": total_time,
    }


def normalize_sector_table(
    db_path: str,
    dry_run: bool = False,
) -> dict:
    """
    规范化 sector_daily 表的 sector_code

    Args:
        db_path: LanceDB 路径
        dry_run: 只分析不写入

    Returns:
        处理统计信息
    """
    table_name = "sector_daily"
    code_column = "sector_code"

    logger.info(f"\n{'='*70}")
    logger.info(f"规范化表: {table_name}")
    logger.info(f"{'='*70}")

    db = lancedb.connect(db_path)

    result = db.list_tables()
    existing_tables = result.tables if hasattr(result, 'tables') else list(result)
    if table_name not in existing_tables:
        logger.warning(f"表 {table_name} 不存在，跳过")
        return {"success": False, "error": "table not found"}

    table = db.open_table(table_name)
    ds = table.to_lance()
    total_rows = table.count_rows()
    logger.info(f"当前行数: {total_rows:,}")

    # sector_daily 的 sector_code 格式可能不同，先检查
    scanner = ds.scanner(columns=[code_column])
    arrow_table = scanner.to_table()
    df_codes = pl.from_arrow(arrow_table)
    sample_codes = df_codes[code_column].unique().to_list()[:10]
    logger.info(f"样本 sector_code: {sample_codes}")

    codes = df_codes[code_column].to_list()
    needs_normalize = sum(1 for c in codes if '.' not in str(c) and len(str(c)) >= 6)

    if needs_normalize == 0:
        logger.info("sector_code 无需规范化")
        return {"success": True, "rows_affected": 0}

    if dry_run:
        return {"success": True, "rows_affected": needs_normalize, "dry_run": True}

    # 读取全量数据并规范化
    scanner = ds.scanner()
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)

    df = df.with_columns(
        normalize_stock_code_polars(df[code_column]).alias(code_column)
    )

    if "trade_date" in df.columns:
        dedup_cols = [code_column, "trade_date"]
        df = df.unique(subset=dedup_cols, keep="last")
        df = df.sort([code_column, "trade_date"])

    db.drop_table(table_name)
    new_table = db.create_table(table_name, df.to_arrow())

    try:
        if "trade_date" in df.columns:
            new_table.create_scalar_index("trade_date", replace=True)
    except Exception as e:
        logger.warning(f"创建索引失败: {e}")

    logger.info(f"结果: {total_rows:,} → {new_table.count_rows():,} 行")
    return {"success": True, "rows_before": total_rows, "rows_after": new_table.count_rows()}


def check_data_gaps(db_path: str) -> dict:
    """
    检查 daily_ohlcv 表中的数据缺口

    Returns:
        缺口信息
    """
    logger.info(f"\n{'='*70}")
    logger.info("检查数据缺口")
    logger.info(f"{'='*70}")

    db = lancedb.connect(db_path)
    table = db.open_table("daily_ohlcv")
    ds = table.to_lance()

    # 获取日期范围
    scanner = ds.scanner(columns=["trade_date"])
    arrow_table = scanner.to_table()
    df = pl.from_arrow(arrow_table)

    dates = df["trade_date"].unique().sort().to_list()
    logger.info(f"日期范围: {dates[0]} ~ {dates[-1]}")
    logger.info(f"交易日数: {len(dates)}")

    # 检查缺口: 找出相邻交易日间隔超过3天的日期
    gaps = []
    for i in range(1, len(dates)):
        prev = dates[i - 1]
        curr = dates[i]
        if hasattr(prev, 'strftime'):
            diff = (curr - prev).days
        else:
            from datetime import datetime
            if isinstance(prev, str):
                prev = datetime.strptime(prev, '%Y-%m-%d').date()
            if isinstance(curr, str):
                curr = datetime.strptime(curr, '%Y-%m-%d').date()
            diff = (curr - prev).days

        if diff > 5:
            gaps.append({
                "start": str(prev),
                "end": str(curr),
                "gap_days": diff,
            })

    if gaps:
        logger.warning(f"发现 {len(gaps)} 个数据缺口:")
        for g in gaps:
            logger.warning(f"  {g['start']} ~ {g['end']} (间隔 {g['gap_days']} 天)")
    else:
        logger.info("未发现明显数据缺口")

    return {"gaps": gaps, "total_trading_days": len(dates)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LanceDB 数据规范化迁移")
    parser.add_argument("--dry-run", action="store_true", help="仅分析不写入")
    parser.add_argument("--skip-factors", action="store_true", help="跳过 factors 表")
    parser.add_argument("--skip-sector", action="store_true", help="跳过 sector_daily 表")
    parser.add_argument("--check-gaps", action="store_true", help="仅检查数据缺口")
    args = parser.parse_args()

    db_path = str(project_root / "data" / "lancedb")

    if args.check_gaps:
        check_data_gaps(db_path)
        return

    logger.info("LanceDB 数据规范化迁移")
    logger.info(f"数据库路径: {db_path}")
    logger.info(f"模式: {'DRY RUN' if args.dry_run else 'LIVE'}")

    results = {}

    # 1. 规范化 daily_ohlcv
    results["daily_ohlcv"] = normalize_table(
        db_path, "daily_ohlcv", "stock_code", args.dry_run
    )

    # 2. 规范化 factors
    if not args.skip_factors:
        results["factors"] = normalize_table(
            db_path, "factors", "stock_code", args.dry_run
        )

    # 3. 规范化 sector_daily
    if not args.skip_sector:
        results["sector_daily"] = normalize_sector_table(db_path, args.dry_run)

    # 4. 检查缺口
    results["gaps"] = check_data_gaps(db_path)

    # 汇总
    logger.info(f"\n{'='*70}")
    logger.info("迁移汇总")
    logger.info(f"{'='*70}")
    for table_name, result in results.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅" if result["success"] else "❌"
            logger.info(f"  {table_name}: {status} {result}")
        else:
            logger.info(f"  {table_name}: {result}")

    logger.info("\n下一步: 运行更新模块补全缺口")
    logger.info("  python -c \"from data_svc.storage.unified_updater import UnifiedDataUpdater; u = UnifiedDataUpdater(); u.update_stock_daily()\"")


if __name__ == "__main__":
    main()
