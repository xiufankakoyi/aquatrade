"""
验证数据完整性
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
from datetime import datetime, timedelta
from loguru import logger

from data_svc.storage.lancedb_reader import LanceDBDataReader


def main():
    reader = LanceDBDataReader()

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    logger.info(f"读取数据: {start_date} ~ {end_date}")

    df = reader.read(
        None,
        start_date=start_date,
        end_date=end_date,
        fields=["stock_code", "trade_date", "close"],
    )

    if df.is_empty():
        logger.warning("没有读取到数据")
        return

    logger.info(f"读取到 {len(df)} 条数据")

    df = df.sort(["stock_code", "trade_date"])

    stock_stats = (
        df.lazy()
        .group_by("stock_code")
        .agg([
            pl.col("trade_date").count().alias("n_rows"),
            pl.col("trade_date").min().alias("min_date"),
            pl.col("trade_date").max().alias("max_date"),
        ])
        .collect()
    )

    logger.info(f"共 {len(stock_stats)} 只股票")

    for threshold in [20, 30, 35, 40, 45, 50]:
        count = stock_stats.filter(pl.col("n_rows") >= threshold).height
        logger.info(f"数据 >= {threshold} 天的股票: {count}")

    sample = stock_stats.sort("n_rows", descending=True).head(10)
    logger.info(f"\n数据最多的10只股票:")
    for row in sample.iter_rows(named=True):
        logger.info(f"  {row['stock_code']}: {row['n_rows']}天, {row['min_date']} ~ {row['max_date']}")

    sample_40 = stock_stats.filter(pl.col("n_rows") >= 40).head(5)
    logger.info(f"\n数据>=40天的样本:")
    for row in sample_40.iter_rows(named=True):
        logger.info(f"  {row['stock_code']}: {row['n_rows']}天, {row['min_date']} ~ {row['max_date']}")


if __name__ == "__main__":
    main()
