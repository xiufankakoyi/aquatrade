"""Local news ingestion and SQLite storage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.concept_lab.concept_loader import RESEARCH_BOUNDARY, project_root
from server.news_lab.news_dedup import dedup_news
from server.news_lab.news_entity_matcher import enrich_news_with_concepts
from server.news_lab.news_source_interface import read_local_news


class LocalNewsStore:
    TABLE_NAME = "local_news"

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path or _config_db_path())

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_table(self) -> None:
        with self._connection() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    publish_time TEXT,
                    url TEXT,
                    related_symbols TEXT,
                    related_concepts TEXT,
                    created_at TEXT,
                    UNIQUE(title, source, publish_time)
                )
                """
            )

    def import_local_file(self, path: str | Path) -> Dict[str, Any]:
        safe_path = _resolve_local_path(path)
        raw_rows = read_local_news(safe_path)
        rows = enrich_news_with_concepts(dedup_news(raw_rows))
        self.ensure_table()
        imported = 0
        with self._connection() as conn:
            for row in rows:
                cursor = conn.execute(
                    f"""
                    INSERT OR IGNORE INTO {self.TABLE_NAME}
                    (title, summary, source, publish_time, url, related_symbols, related_concepts, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("title"),
                        row.get("summary"),
                        row.get("source"),
                        row.get("publish_time"),
                        row.get("url"),
                        json.dumps(row.get("related_symbols") or [], ensure_ascii=False),
                        json.dumps(row.get("related_concepts") or [], ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                imported += int(cursor.rowcount or 0)
        return {
            "source_path": str(safe_path),
            "rows_read": len(raw_rows),
            "rows_after_dedup": len(rows),
            "rows_imported": imported,
            "research_boundary": RESEARCH_BOUNDARY,
        }

    def query_recent(self, limit: int = 100, concept_id: str | None = None) -> List[Dict[str, Any]]:
        self.ensure_table()
        sql = f"SELECT * FROM {self.TABLE_NAME}"
        params: List[Any] = []
        if concept_id:
            sql += " WHERE related_concepts LIKE ?"
            params.append(f'%"{concept_id}"%')
        sql += " ORDER BY publish_time DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]


def _resolve_local_path(path: str | Path) -> Path:
    raw_path = Path(path)
    root = project_root().resolve()
    target = raw_path if raw_path.is_absolute() else root / raw_path
    resolved = target.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("news import path must be inside the AQUATRADE project")
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def _config_db_path() -> Path:
    fallback = project_root() / "data" / "database" / "stock_data.db"
    try:
        from config.config import Config

        return Path(getattr(Config, "DB_PATH", fallback))
    except Exception:
        return fallback


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    for key in ["related_symbols", "related_concepts"]:
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except json.JSONDecodeError:
            item[key] = []
    return item
