"""Load local concept definitions and stock evidence mappings."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


RESEARCH_BOUNDARY = "仅展示本地维护的概念资料、证据和市场统计，不构成买入、卖出或仓位建议。"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_knowledge_dir() -> Path:
    return project_root() / "knowledge"


class ConceptLoader:
    """Read concept knowledge from local files without external services."""

    def __init__(
        self,
        concepts_path: Optional[str | Path] = None,
        mapping_path: Optional[str | Path] = None,
    ) -> None:
        knowledge_dir = default_knowledge_dir()
        self.concepts_path = Path(concepts_path or knowledge_dir / "concepts.yaml")
        self.mapping_path = Path(mapping_path or knowledge_dir / "stock_concept_mapping.csv")

    def load_concepts(self) -> List[Dict[str, Any]]:
        if not self.concepts_path.exists():
            return []
        text = self.concepts_path.read_text(encoding="utf-8-sig").strip()
        if not text:
            return []
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("concepts.yaml must contain a list of concept objects")
        return [_normalize_concept(item) for item in data if isinstance(item, dict)]

    def load_mapping(self) -> List[Dict[str, Any]]:
        if not self.mapping_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not (row.get("symbol") or "").strip():
                    continue
                rows.append(_normalize_mapping(row))
        return rows

    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        for concept in self.load_concepts():
            if concept["concept_id"] == concept_id:
                return concept
        return None

    def search_concepts(self, keyword: str) -> List[Dict[str, Any]]:
        query = (keyword or "").strip().lower()
        if not query:
            return self.load_concepts()
        results = []
        for concept in self.load_concepts():
            haystack = " ".join(
                [
                    concept["concept_id"],
                    concept["concept_name"],
                    " ".join(concept["aliases"]),
                    " ".join(concept["keywords"]),
                    concept["description"],
                ]
            ).lower()
            if query in haystack:
                results.append(concept)
        return results


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("；", ";").replace(",", ";").split(";") if part.strip()]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "sample"}


def _normalize_concept(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "concept_id": str(item.get("concept_id") or "").strip(),
        "concept_name": str(item.get("concept_name") or "").strip(),
        "aliases": _as_list(item.get("aliases")),
        "parent_concepts": _as_list(item.get("parent_concepts")),
        "industry_chain": _as_list(item.get("industry_chain")),
        "keywords": _as_list(item.get("keywords")),
        "description": str(item.get("description") or "").strip(),
    }


def _normalize_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "symbol": str(row.get("symbol") or "").strip(),
        "stock_name": str(row.get("stock_name") or "").strip(),
        "concept_id": str(row.get("concept_id") or "").strip(),
        "chain_position": str(row.get("chain_position") or "").strip(),
        "relevance_score": _as_float(row.get("relevance_score")),
        "purity_score": _as_float(row.get("purity_score")),
        "evidence_type": str(row.get("evidence_type") or "").strip(),
        "evidence_text": str(row.get("evidence_text") or "").strip(),
        "evidence_source": str(row.get("evidence_source") or "").strip(),
        "updated_at": str(row.get("updated_at") or "").strip(),
        "notes": str(row.get("notes") or "").strip(),
        "is_sample": _as_bool(row.get("is_sample")),
    }
