"""PatternRadar research APIs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from server.pattern_lab.pattern_templates import get_pattern_templates

pattern_bp = Blueprint("patterns", __name__, url_prefix="/api/patterns")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


def _require_date(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not DATE_RE.match(text):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return text


def _parse_symbols(value: Any) -> Optional[List[str]]:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


@pattern_bp.route("/templates", methods=["GET"])
def templates():
    return jsonify(
        {
            "success": True,
            "data": get_pattern_templates(),
            "research_boundary": "仅用于形态研究和样本统计，不构成买入、卖出或仓位建议。",
        }
    )


@pattern_bp.route("/search", methods=["POST"])
def search_patterns():
    payload = request.get_json(silent=True) or {}
    try:
        pattern_id = str(payload.get("pattern_id") or "").strip()
        if not pattern_id:
            raise ValueError("pattern_id is required")
        start_date = _require_date(payload.get("start_date"), "start_date")
        end_date = _require_date(payload.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    symbols = _parse_symbols(payload.get("symbols"))
    params: Dict[str, Any] = payload.get("params") or {}
    limit = int(payload.get("limit") or 100)

    try:
        if payload.get("auto_generate") is True:
            from server.event_engine.event_store import generate_daily_event_tags

            generate_daily_event_tags(start_date, end_date, symbols=symbols)

        from server.pattern_lab.pattern_scanner import PatternScanner

        report = PatternScanner().search(
            pattern_id=pattern_id,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            params=params,
            limit=limit,
        )
        return jsonify({"success": True, "data": report})
    except Exception as exc:
        return _error(str(exc), status=500)


@pattern_bp.route("/backtest", methods=["POST"])
def backtest_pattern():
    payload = request.get_json(silent=True) or {}
    try:
        pattern_id = str(payload.get("pattern_id") or "").strip()
        if not pattern_id:
            raise ValueError("pattern_id is required")
        start_date = _require_date(payload.get("start_date"), "start_date")
        end_date = _require_date(payload.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    try:
        from server.pattern_lab.pattern_scanner import PatternScanner

        report = PatternScanner().search(
            pattern_id=pattern_id,
            start_date=start_date,
            end_date=end_date,
            symbols=_parse_symbols(payload.get("symbols")),
            params=payload.get("params") or {},
            limit=int(payload.get("limit") or 500),
        )
        return jsonify(
            {
                "success": True,
                "data": {
                    "pattern_id": report["pattern_id"],
                    "pattern_name": report["pattern_name"],
                    "start_date": report["start_date"],
                    "end_date": report["end_date"],
                    "params": report["params"],
                    "summary": report["summary"],
                    "success_samples": report["success_samples"],
                    "failure_samples": report["failure_samples"],
                    "research_boundary": report["research_boundary"],
                },
            }
        )
    except Exception as exc:
        return _error(str(exc), status=500)


@pattern_bp.route("/cases", methods=["GET"])
def pattern_cases():
    pattern_id = request.args.get("pattern_id", "strong_break_reversal")
    case_type = request.args.get("case_type", "all")
    try:
        start_date = _require_date(request.args.get("start_date"), "start_date")
        end_date = _require_date(request.args.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    try:
        from server.pattern_lab.pattern_scanner import PatternScanner

        report = PatternScanner().search(
            pattern_id=pattern_id,
            start_date=start_date,
            end_date=end_date,
            symbols=_parse_symbols(request.args.get("symbols")),
            params={},
            limit=request.args.get("limit", 100, type=int),
        )
        if case_type == "success":
            data = report["success_samples"]
        elif case_type == "failure":
            data = report["failure_samples"]
        elif case_type == "current":
            data = report["current_candidates"]
        else:
            data = report["results"]
        return jsonify({"success": True, "data": data, "count": len(data)})
    except Exception as exc:
        return _error(str(exc), status=500)


@pattern_bp.route("/symbol/<symbol>/events", methods=["GET"])
def symbol_events(symbol: str):
    try:
        start_date = _require_date(request.args.get("start_date"), "start_date")
        end_date = _require_date(request.args.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    try:
        from server.event_engine.event_store import DailyEventTagStore

        rows = DailyEventTagStore().query_event_tags(
            start_date=start_date,
            end_date=end_date,
            symbols=[symbol],
            filters=None,
            limit=request.args.get("limit", 1000, type=int),
        )
        return jsonify({"success": True, "data": rows, "count": len(rows)})
    except Exception as exc:
        return _error(str(exc), status=500)
