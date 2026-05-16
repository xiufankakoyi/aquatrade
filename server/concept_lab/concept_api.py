"""Flask blueprint for ConceptResearch APIs."""

from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from server.concept_lab.concept_loader import ConceptLoader, RESEARCH_BOUNDARY
from server.concept_lab.concept_score_engine import score_stock_mappings


concept_bp = Blueprint("concepts", __name__, url_prefix="/api/concepts")


def _response(data: Any, message: str | None = None, count: int | None = None):
    payload: Dict[str, Any] = {
        "success": True,
        "data": data,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    if message:
        payload["message"] = message
    if count is not None:
        payload["count"] = count
    return jsonify(payload)


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message, "research_boundary": RESEARCH_BOUNDARY}), status


@concept_bp.route("", methods=["GET"])
@concept_bp.route("/", methods=["GET"])
def list_concepts():
    loader = ConceptLoader()
    concepts = loader.load_concepts()
    return _response(concepts, count=len(concepts))


@concept_bp.route("/search", methods=["POST"])
def search_concepts():
    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("keyword") or payload.get("q") or "").strip()
    loader = ConceptLoader()
    concepts = loader.search_concepts(keyword)
    return _response(concepts, count=len(concepts))


@concept_bp.route("/<concept_id>", methods=["GET"])
def get_concept(concept_id: str):
    loader = ConceptLoader()
    concept = loader.get_concept(concept_id)
    if not concept:
        return _error(f"unknown concept_id: {concept_id}", 404)
    return _response(concept)


@concept_bp.route("/<concept_id>/stocks", methods=["GET"])
def get_concept_stocks(concept_id: str):
    loader = ConceptLoader()
    if not loader.get_concept(concept_id):
        return _error(f"unknown concept_id: {concept_id}", 404)
    rows = [row for row in loader.load_mapping() if row.get("concept_id") == concept_id]
    scored = score_stock_mappings(rows)
    message = None if scored else "暂无本地证据"
    return _response(scored, message=message, count=len(scored))


@concept_bp.route("/<concept_id>/market-confirm", methods=["GET"])
def get_market_confirm(concept_id: str):
    loader = ConceptLoader()
    if not loader.get_concept(concept_id):
        return _error(f"unknown concept_id: {concept_id}", 404)
    rows = [row for row in loader.load_mapping() if row.get("concept_id") == concept_id]
    symbols = [row["symbol"] for row in rows if row.get("symbol")]
    market_rows: List[Dict[str, Any]] = []
    if symbols:
        market_rows = _query_recent_market_confirm(symbols)
    message = None if market_rows else "暂无本地市场确认数据"
    return _response(market_rows, message=message, count=len(market_rows))


def _query_recent_market_confirm(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        from server.event_engine.event_store import DailyEventTagStore

        rows = DailyEventTagStore().query_event_tags("1900-01-01", "2999-12-31", symbols=symbols, limit=5000)
    except Exception:
        return []

    latest_by_symbol: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        symbol = str(row.get("stock_code") or "")
        if symbol and (symbol not in latest_by_symbol or str(row.get("trade_date")) > str(latest_by_symbol[symbol].get("trade_date"))):
            latest_by_symbol[symbol] = row

    result = []
    for symbol, row in latest_by_symbol.items():
        score = 0.0
        if row.get("is_limit_up"):
            score += 0.45
        if row.get("is_big_up"):
            score += 0.25
        if row.get("volume_burst"):
            score += 0.2
        if float(row.get("amount_rank_20d") or 0.0) >= 0.8:
            score += 0.1
        result.append(
            {
                "symbol": symbol,
                "trade_date": row.get("trade_date"),
                "change_pct": row.get("change_pct"),
                "amount": row.get("amount"),
                "is_limit_up": bool(row.get("is_limit_up")),
                "volume_burst": bool(row.get("volume_burst")),
                "market_confirm_score": round(min(score, 1.0), 4),
            }
        )
    return sorted(result, key=lambda item: item["market_confirm_score"], reverse=True)
