"""News title deduplication."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple


def dedup_news(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[Tuple[str, str, str]] = set()
    unique = []
    for row in rows:
        key = (
            _normalize_title(str(row.get("title") or "")),
            str(row.get("source") or "").strip().lower(),
            str(row.get("publish_time") or "")[:10],
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title).strip().lower()
