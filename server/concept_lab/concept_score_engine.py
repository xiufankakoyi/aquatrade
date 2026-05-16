"""Scoring rules for local concept evidence."""

from __future__ import annotations

from typing import Any, Dict, List


EVIDENCE_TYPE_SCORE = {
    "announcement": 1.0,
    "annual_report": 1.0,
    "semi_annual_report": 0.95,
    "official_website": 0.75,
    "irm": 0.65,
    "exchange_qna": 0.65,
    "concept_board": 0.35,
    "sample": 0.0,
    "": 0.0,
}


def evidence_score(evidence_type: str) -> float:
    return EVIDENCE_TYPE_SCORE.get((evidence_type or "").strip().lower(), 0.2)


def calculate_concept_score(mapping: Dict[str, Any], market_confirm_score: float = 0.0) -> float:
    relevance = float(mapping.get("relevance_score") or 0.0)
    purity = float(mapping.get("purity_score") or 0.0)
    evidence = evidence_score(str(mapping.get("evidence_type") or ""))
    score = relevance * 0.45 + purity * 0.25 + evidence * 0.15 + market_confirm_score * 0.15
    return round(max(0.0, min(score, 1.0)), 4)


def score_stock_mappings(rows: List[Dict[str, Any]], market_scores: Dict[str, float] | None = None) -> List[Dict[str, Any]]:
    market_scores = market_scores or {}
    scored = []
    for row in rows:
        symbol = str(row.get("symbol") or "")
        market_score = float(market_scores.get(symbol, 0.0))
        item = dict(row)
        item["evidence_score"] = round(evidence_score(str(row.get("evidence_type") or "")), 4)
        item["market_confirm_score"] = round(market_score, 4)
        item["concept_score"] = calculate_concept_score(row, market_score)
        scored.append(item)
    return sorted(scored, key=lambda item: item.get("concept_score", 0.0), reverse=True)
