#!/usr/bin/env python
"""Runtime smoke test for research workbench routes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app import app


def main() -> int:
    client = app.test_client()
    strategies_response = client.get("/api/strategies")
    strategies_payload = strategies_response.get_json(silent=True) or {}
    strategies = strategies_payload.get("data", [])
    strategy_id = ""
    if isinstance(strategies, list) and strategies:
        selected = next(
            (item for item in strategies if item.get("id") == "test_strategy"),
            strategies[0],
        )
        strategy_id = str(selected.get("id") or "")

    checks = [
        ("GET", "/api/strategies", None),
        ("GET", "/api/latest_price?symbols=000001.SZ&date=2026-01-01", None),
        ("GET", "/api/stock_posts_by_keyword?keyword=smoke-test&limit=1", None),
        ("POST", "/api/screener/field_stats", {"field": "close", "date": "1900-01-01"}),
        ("POST", "/api/screener/export", {"date": "1900-01-01"}),
        ("POST", "/api/benchmark/NO_SUCH_CODE/equity", {}),
        ("GET", "/api/data/health", None),
        ("GET", "/api/quant-flow/latest", None),
    ]
    if strategy_id:
        checks.append(("GET", f"/api/strategies/{quote(strategy_id, safe='')}/params", None))
        checks.append(("POST", f"/api/strategies/{quote(strategy_id, safe='')}/quality", {}))

    results = []
    failed = not strategy_id
    for method, path, body in checks:
        response = client.open(path, method=method, json=body)
        item = {
            "method": method,
            "path": path,
            "status": response.status_code,
            "not_404": response.status_code != 404,
            "not_5xx": response.status_code < 500,
        }
        results.append(item)
        if response.status_code == 404 or response.status_code >= 500:
            failed = True

    required_rules = {
        "/api/latest_price",
        "/api/stock_posts_by_keyword",
        "/api/screener/field_stats",
        "/api/screener/export",
        "/api/benchmark/<code>/equity",
        "/api/strategies/<strategy_id>/params",
        "/api/strategies/<strategy_id>/quality",
    }
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    missing_rules = sorted(required_rules - rules)
    if missing_rules:
        failed = True

    print(
        json.dumps(
            {
                "success": not failed,
                "strategy_id": strategy_id or None,
                "results": results,
                "missing_rules": missing_rules,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
