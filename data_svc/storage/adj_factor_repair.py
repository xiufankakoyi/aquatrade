"""
复权因子补全服务
================

使用 Tushare API 补充缺失的 adj_factor 数据。

问题：数据库中约 5% 的 adj_factor 为空
解决：通过 Tushare adj_factor API 批量获取并补充

使用方式：
    python -c "from data_svc.storage.adj_factor_repair import repair_adj_factors; repair_adj_factors()"
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
from datetime import datetime, timedelta
from typing import Optional

import polars as pl
import pandas as pd
import lancedb

from config.logger import get_logger
from config.config import Config

logger = get_logger(__name__)


def get_lancedb_path() -> str:
    """获取 LanceDB 路径"""
    db_path = getattr(Config, 'LANCEDB_PATH', None)
    if db_path is None:
        db_path = str(project_root / "data" / "lancedb")
    return db_path


def find_missing_adj_factors(db_path: Optional[str] = None) -> pl.DataFrame:
    """
    找出 adj_factor 为空的记录

    Returns:
        Polars DataFrame，包含 stock_code 和空缺 adj_factor 的 trade_date
    """
    if db_path is None:
        db_path = get_lancedb_path()

    db = lancedb.connect(db_path)
    table = db.open_table("daily_ohlcv")
    df = pl.from_arrow(table.to_arrow())

    missing = df.filter(pl.col("adj_factor").is_null() | (pl.col("adj_factor") == 0))

    if missing.is_empty():
        logger.info("[AdjFactorRepair] 没有缺失的 adj_factor")
        return missing

    logger.info(f"[AdjFactorRepair] 发现 {len(missing):,} 条缺失 adj_factor 的记录")

    return missing.select(["stock_code", "trade_date"]).unique()


def fetch_adj_factor_from_tushare(
    ts_code: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """从 Tushare 获取单只股票的复权因子"""
    try:
        import tushare as ts
        pro = ts.pro_api(Config.TUSHARE_TOKEN)
        df = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
        return df
    except Exception as e:
        logger.warning(f"[AdjFactorRepair] 获取 {ts_code} 复权因子失败: {e}")
        return pd.DataFrame()


def repair_adj_factors(batch_size: int = 100, db_path: Optional[str] = None) -> dict:
    """
    补全缺失的 adj_factor

    Args:
        batch_size: 每批处理的股票数量
        db_path: LanceDB 路径

    Returns:
        dict with keys: success, records_repaired, elapsed_seconds
    """
    start_time = time.time()

    if db_path is None:
        db_path = get_lancedb_path()

    logger.info("[AdjFactorRepair] 开始补全 adj_factor...")

    missing_df = find_missing_adj_factors(db_path)

    if missing_df.is_empty():
        return {"success": True, "records_repaired": 0, "elapsed_seconds": 0}

    stock_dates = missing_df.group_by("stock_code").agg([
        pl.col("trade_date").min().alias("start_date"),
        pl.col("trade_date").max().alias("end_date")
    ])

    total_stocks = len(stock_dates)
    repaired_count = 0

    db = lancedb.connect(db_path)
    table = db.open_table("daily_ohlcv")
    existing_df = pl.from_arrow(table.to_arrow())

    for i, row in enumerate(stock_dates.iter_rows(named=True)):
        if (i + 1) % 20 == 0:
            logger.info(f"[AdjFactorRepair] 进度: {i+1}/{total_stocks}")

        ts_code = row["stock_code"]
        start_date = row["start_date"].strftime("%Y%m%d") if hasattr(row["start_date"], 'strftime') else str(row["start_date"])[:10].replace("-", "")
        end_date = row["end_date"].strftime("%Y%m%d") if hasattr(row["end_date"], 'strftime') else str(row["end_date"])[:10].replace("-", "")

        try:
            adj_df = fetch_adj_factor_from_tushare(ts_code, start_date, end_date)

            if adj_df is None or adj_df.empty:
                continue

            adj_pl = pl.from_pandas(adj_df)
            adj_pl = adj_pl.rename({"trade_date": "trade_date_adj", "adj_factor": "adj_factor_new"})

            existing_df = existing_df.join(
                adj_pl,
                left_on=["stock_code", "trade_date"],
                right_on=["ts_code", "trade_date_adj"],
                how="left"
            )

            existing_df = existing_df.with_columns([
                pl.when(pl.col("adj_factor_new").is_not_null())
                .then(pl.col("adj_factor_new"))
                .otherwise(pl.col("adj_factor"))
                .alias("adj_factor")
            ])

            existing_df = existing_df.drop("adj_factor_new", "ts_code")

        except Exception as e:
            logger.warning(f"[AdjFactorRepair] 处理 {ts_code} 失败: {e}")
            continue

    db.drop_table("daily_ohlcv")
    db.create_table("daily_ohlcv", existing_df.to_arrow())

    elapsed = time.time() - start_time
    repaired_count = len(existing_df.filter(pl.col("adj_factor").is_null() | (pl.col("adj_factor") == 0)))

    logger.info(f"[AdjFactorRepair] 补全完成，剩余空缺: {repaired_count:,}, 耗时: {elapsed:.1f}s")

    return {
        "success": True,
        "records_repaired": repaired_count,
        "elapsed_seconds": elapsed
    }


def quick_fill_adj_factor(db_path: Optional[str] = None) -> int:
    """
    快速填充策略：用前值填充缺失的 adj_factor

    对于停牌或其他原因导致的数据缺失，使用 forward fill 填充
    这比从 Tushare 重新获取更快

    Args:
        db_path: LanceDB 路径

    Returns:
        填充的记录数
    """
    if db_path is None:
        db_path = get_lancedb_path()

    logger.info("[AdjFactorRepair] 使用前值填充缺失的 adj_factor...")

    db = lancedb.connect(db_path)
    table = db.open_table("daily_ohlcv")
    df = pl.from_arrow(table.to_arrow())

    original_nulls = df.filter(pl.col("adj_factor").is_null() | (pl.col("adj_factor") == 0)).height

    df = df.sort(["stock_code", "trade_date"])
    df = df.with_columns(
        pl.col("adj_factor").forward_fill().over("stock_code").alias("adj_factor_filled")
    )
    df = df.with_columns(
        pl.when(pl.col("adj_factor_filled").is_null())
        .then(1.0)
        .otherwise(pl.col("adj_factor_filled"))
        .alias("adj_factor")
    )
    df = df.drop("adj_factor_filled")

    db.drop_table("daily_ohlcv")
    db.create_table("daily_ohlcv", df.to_arrow())

    remaining_nulls = df.filter(pl.col("adj_factor").is_null() | (pl.col("adj_factor") == 0)).height

    logger.info(f"[AdjFactorRepair] 填充完成: {original_nulls:,} -> {remaining_nulls:,}")

    return original_nulls - remaining_nulls


if __name__ == "__main__":
    print("=" * 60)
    print("复权因子补全服务")
    print("=" * 60)

    print("\n1. 快速前值填充（推荐先执行）:")
    filled = quick_fill_adj_factor()
    print(f"   填充了 {filled:,} 条记录")

    print("\n2. 从 Tushare 补全剩余缺失:")
    result = repair_adj_factors()
    print(f"   结果: {result}")
