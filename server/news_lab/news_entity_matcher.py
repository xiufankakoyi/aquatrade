"""Keyword matcher from local news titles to local concepts."""

from __future__ import annotations

from typing import Any, Dict, List

from server.concept_lab.concept_loader import ConceptLoader


def match_related_concepts(news_item: Dict[str, Any], loader: ConceptLoader | None = None) -> List[str]:
    loader = loader or ConceptLoader()
    text = f"{news_item.get('title') or ''} {news_item.get('summary') or ''}".lower()
    matches = []
    for concept in loader.load_concepts():
        terms = [concept["concept_name"], *concept["aliases"], *concept["keywords"]]
        if any(term and str(term).lower() in text for term in terms):
            matches.append(concept["concept_id"])
    return sorted(set(matches))


def enrich_news_with_concepts(rows: List[Dict[str, Any]], loader: ConceptLoader | None = None) -> List[Dict[str, Any]]:
    enriched = []
    for row in rows:
        item = dict(row)
        existing = _parse_list(item.get("related_concepts"))
        matched = match_related_concepts(item, loader)
        item["related_concepts"] = sorted(set(existing + matched))
        item["related_symbols"] = _parse_list(item.get("related_symbols"))
        enriched.append(item)
    return enriched


def _parse_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("；", ";").replace(",", ";").split(";") if part.strip()]
