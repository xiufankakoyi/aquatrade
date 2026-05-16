"""Daily event tag APIs for PatternRadar research."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from server.event_engine.event_schema import (
    DEFAULT_THRESHOLDS,
    EVENT_BOOL_COLUMNS,
    EVENT_NUMERIC_COLUMNS,
    EVENT_OUTPUT_COLUMNS,
)

event_bp = Blueprint("events", __name__, url_prefix="/api/events")

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


def _parse_filters_from_query() -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    for key, value in request.args.items():
        if key in {"start_date", "end_date", "symbols", "limit"}:
            continue
        if key in EVENT_BOOL_COLUMNS:
            filters[key] = value.lower() in {"1", "true", "yes", "y"}
        elif key in EVENT_NUMERIC_COLUMNS or key in {"change_pct", "amount", "volume", "total_mv", "turnover_rate"}:
            try:
                filters[key] = float(value)
            except ValueError:
                continue
        elif key.endswith("__gte") or key.endswith("__lte"):
            try:
                filters[key] = float(value)
            except ValueError:
                continue
    return filters


@event_bp.route("/schema", methods=["GET"])
def get_event_schema():
    return jsonify(
        {
            "success": True,
            "data": {
                "columns": EVENT_OUTPUT_COLUMNS,
                "bool_columns": EVENT_BOOL_COLUMNS,
                "numeric_columns": EVENT_NUMERIC_COLUMNS,
                "thresholds": DEFAULT_THRESHOLDS.to_dict(),
            },
        }
    )


@event_bp.route("/generate", methods=["POST"])
def generate_events():
    payload = request.get_json(silent=True) or {}
    try:
        start_date = _require_date(payload.get("start_date"), "start_date")
        end_date = _require_date(payload.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    symbols = _parse_symbols(payload.get("symbols"))

    try:
        from server.event_engine.event_store import generate_daily_event_tags

        result = generate_daily_event_tags(start_date, end_date, symbols=symbols)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return _error(str(exc), status=500)


@event_bp.route("/query", methods=["POST"])
def query_events_post():
    payload = request.get_json(silent=True) or {}
    try:
        start_date = _require_date(payload.get("start_date"), "start_date")
        end_date = _require_date(payload.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    symbols = _parse_symbols(payload.get("symbols"))
    filters = payload.get("filters") or {}
    limit = int(payload.get("limit") or 5000)

    try:
        from server.event_engine.event_store import DailyEventTagStore

        rows = DailyEventTagStore().query_event_tags(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            filters=filters,
            limit=limit,
        )
        return jsonify({"success": True, "data": rows, "count": len(rows)})
    except Exception as exc:
        return _error(str(exc), status=500)


@event_bp.route("/tags", methods=["GET"])
def query_events_get():
    try:
        start_date = _require_date(request.args.get("start_date"), "start_date")
        end_date = _require_date(request.args.get("end_date"), "end_date")
    except ValueError as exc:
        return _error(str(exc))

    symbols = _parse_symbols(request.args.get("symbols"))
    filters = _parse_filters_from_query()
    limit = request.args.get("limit", 5000, type=int)

    try:
        from server.event_engine.event_store import DailyEventTagStore

        rows = DailyEventTagStore().query_event_tags(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            filters=filters,
            limit=limit,
        )
        return jsonify({"success": True, "data": rows, "count": len(rows)})
    except Exception as exc:
        return _error(str(exc), status=500)
