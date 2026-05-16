"""Local CSV/JSON news source reader."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


NEWS_FIELDS = [
    "title",
    "summary",
    "source",
    "publish_time",
    "url",
    "related_symbols",
    "related_concepts",
]


def read_local_news(path: str | Path) -> List[Dict[str, Any]]:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(source_path)
    if suffix == ".json":
        return _read_json(source_path)
    raise ValueError("only local CSV or JSON news files are supported")


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_normalize(row) for row in reader if (row.get("title") or "").strip()]


def _read_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("data", [])
    if not isinstance(data, list):
        raise ValueError("JSON news file must contain a list or a {data: [...]} object")
    return [_normalize(row) for row in data if isinstance(row, dict) and str(row.get("title") or "").strip()]


def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
    return {field: row.get(field, "") for field in NEWS_FIELDS}
