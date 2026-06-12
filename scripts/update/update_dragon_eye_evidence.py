#!/usr/bin/env python
"""检查或更新 DragonEye 本地结构化证据。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _latest_trade_date() -> str:
    try:
        from data_svc.storage.lancedb_reader import LanceDBDataReader

        _earliest, latest = LanceDBDataReader().get_date_range()
        return str(latest)[:10] if latest else ""
    except Exception:
        return ""


def run(target_date: str, *, inspect_only: bool, backfill: bool) -> dict:
    from data_svc.ingestion.dragon_eye_adapter import DragonEyeAdapter

    adapter = DragonEyeAdapter()
    before = adapter.inspect_local_date(target_date)
    update_result = None
    if not inspect_only:
        from data_svc.storage.unified_updater import UnifiedDataUpdater

        update_result = UnifiedDataUpdater().update_dragon_eye(
            target_date=target_date,
            backfill=backfill,
        )
    after = adapter.inspect_local_date(target_date)

    # 区分完整成功、partial_success 和 failure
    if after.get("complete"):
        outcome = "success"
        message = "DragonEye 证据完整"
    elif after.get("has_ladder") or after.get("has_limit_up"):
        # 至少有一类数据：明确告知缺什么，禁止伪装成完整
        outcome = "partial_success"
        missing = after.get("missing_parts") or []
        message = (
            "DragonEye 仅有局部数据"
            + (f"，缺 {', '.join(missing)}" if missing else "")
            + "；不能生成完整情绪判断"
        )
    else:
        outcome = "failure"
        message = "DragonEye 仍缺少本地结构化组件"

    return {
        "target_date": target_date,
        "inspect_only": inspect_only,
        "before": before,
        "update_result": update_result,
        "after": after,
        "outcome": outcome,
        "partial_success": outcome == "partial_success",
        "complete": bool(after.get("complete")),
        "completeness_score": after.get("completeness_score", 0.0),
        "missing_parts": after.get("missing_parts", []),
        "has_ladder": after.get("has_ladder", False),
        "has_limit_up": after.get("has_limit_up", False),
        "has_sentiment": after.get("has_sentiment", False),
        "has_theme_flow": after.get("has_theme_flow", False),
        "evidence_date": after.get("evidence_date", target_date),
        "message": message,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="更新 DragonEye 本地证据")
    parser.add_argument("--target-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    args = parser.parse_args(argv)
    target_date = args.target_date or _latest_trade_date()
    if not target_date:
        print(json.dumps({"outcome": "failure", "message": "无法确定目标交易日"}, ensure_ascii=False))
        return 1
    result = run(
        target_date,
        inspect_only=bool(args.inspect_only),
        backfill=bool(args.backfill),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # success -> 0，partial_success -> 2（必须显式被上层感知），failure -> 3
    return {"success": 0, "partial_success": 2, "failure": 3}.get(
        result["outcome"], 4
    )


if __name__ == "__main__":
    raise SystemExit(main())
