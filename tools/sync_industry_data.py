"""
产业链数据同步脚本

用法:
    python tools/sync_industry_data.py --chain optical_communication --date 2026-05-16
    python tools/sync_industry_data.py --all --date 2026-05-16

执行流程:
1. 加载 industry_chains yaml
2. 加载 manual provider
3. 可选加载 Tushare
4. 可选加载 AKShare
5. 归一化 symbol
6. 保存 concept_members.parquet
7. 保存 company_evidence.parquet
8. 保存 stock_market_snapshot.parquet
9. 计算 node_market_metrics.parquet
10. 输出同步摘要
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server.data_sync.sync_industry_data import IndustryDataSync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="产业链数据同步工具")
    parser.add_argument("--chain", type=str, default=None, help="指定产业链 ID")
    parser.add_argument("--all", action="store_true", help="同步所有产业链")
    parser.add_argument("--date", type=str, default=None, help="交易日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    if not args.chain and not args.all:
        parser.print_help()
        return 1

    chain_id = None if args.all else args.chain
    sync = IndustryDataSync()
    summary = sync.sync_all(chain_id=chain_id, trade_date=args.date)

    logger.info("=" * 50)
    logger.info("同步摘要")
    logger.info("=" * 50)
    for key, value in summary.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
