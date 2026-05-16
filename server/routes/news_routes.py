"""Local news research APIs."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.concept_lab.concept_loader import RESEARCH_BOUNDARY
from server.news_lab.news_ingest import LocalNewsStore


news_bp = Blueprint("news", __name__, url_prefix="/api/news")


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message, "research_boundary": RESEARCH_BOUNDARY}), status


@news_bp.route("/import-local", methods=["POST"])
def import_local_news():
    payload = request.get_json(silent=True) or {}
    path = str(payload.get("path") or "").strip()
    if not path:
        return _error("path is required")
    try:
        summary = LocalNewsStore().import_local_file(path)
        return jsonify({"success": True, "data": summary, "research_boundary": RESEARCH_BOUNDARY})
    except Exception as exc:
        return _error(str(exc), status=500)


@news_bp.route("/recent", methods=["GET"])
def recent_news():
    try:
        rows = LocalNewsStore().query_recent(limit=request.args.get("limit", 100, type=int))
        return jsonify({"success": True, "data": rows, "count": len(rows), "research_boundary": RESEARCH_BOUNDARY})
    except Exception as exc:
        return _error(str(exc), status=500)


@news_bp.route("/concepts/<concept_id>", methods=["GET"])
def concept_news(concept_id: str):
    try:
        rows = LocalNewsStore().query_recent(limit=request.args.get("limit", 100, type=int), concept_id=concept_id)
        return jsonify({"success": True, "data": rows, "count": len(rows), "research_boundary": RESEARCH_BOUNDARY})
    except Exception as exc:
        return _error(str(exc), status=500)
