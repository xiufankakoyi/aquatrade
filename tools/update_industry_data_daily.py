"""Run Data Auto Update v1 for AQUATRADE IndustryChainRadar.

Usage:
    python tools/update_industry_data_daily.py --date today
    python tools/update_industry_data_daily.py --date 2026-05-16
    python tools/update_industry_data_daily.py --chain optical_communication
    python tools/update_industry_data_daily.py --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server.data_sync.sync_industry_data import IndustryDataSync

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="AQUATRADE IndustryChainRadar 每日自动更新")
    parser.add_argument("--date", type=str, default="today", help="交易日期：today 或 YYYY-MM-DD")
    parser.add_argument("--chain", type=str, default=None, help="只更新指定产业链 ID")
    parser.add_argument("--all", action="store_true", help="更新所有产业链")
    args = parser.parse_args()

    chain_id = None if args.all else args.chain
    if not chain_id and not args.all:
        chain_id = "optical_communication"

    sync = IndustryDataSync()
    summary = sync.sync_all(chain_id=chain_id, trade_date=args.date)
    _print_report(summary)
    return 0 if summary.get("status") in {"success", "no_chains"} else 1


def _print_report(summary: dict[str, Any]) -> None:
    print("\n=== IndustryChainRadar Data Auto Update v1 ===")
    print(f"状态: {summary.get('status')}")
    print(f"交易日期: {summary.get('trade_date')}")
    print(f"产业链: {', '.join(summary.get('chains_synced', []))}")
    print(f"行情股票数: {summary.get('market_snapshot_count', 0)}")
    print(f"概念板块数: {summary.get('concept_boards_count', 0)}")
    print(f"概念成分数: {summary.get('concept_board_members_count', 0)}")
    print(f"涨停池数量: {summary.get('limit_up_count', 0)}")
    print(f"节点候选数: {summary.get('node_candidates_count', 0)}")
    print(f"节点指标数: {summary.get('node_metrics_count', 0)}")
    print("\n最热节点:")
    for item in summary.get("top_nodes", []):
        print(f"  - {item.get('chain_id')} / {item.get('node_name')}: {item.get('hot_score')} ({item.get('market_strength')})")
    print("\n数据源成功:")
    for item in summary.get("provider_report", {}).get("success", []):
        print(f"  - {item.get('method')} -> {item.get('provider')} ({item.get('rows')} 行)")
    failed = summary.get("provider_report", {}).get("failed", [])
    if failed:
        print("\n失败或空数据源:")
        for item in failed[:30]:
            context = f" [{item.get('context')}]" if item.get("context") else ""
            print(f"  - {item.get('method')}{context} -> {item.get('provider')}: {item.get('error')}")
        if len(failed) > 30:
            print(f"  - 其余 {len(failed) - 30} 条详见 data/industry/data_source_log.parquet")
    print("\n同步摘要 JSON:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
