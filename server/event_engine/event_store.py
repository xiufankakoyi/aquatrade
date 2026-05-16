"""Persistence and query layer for daily event tags."""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd

from server.event_engine.daily_event_tagger import tag_daily_events
from server.event_engine.event_schema import (
    DEFAULT_THRESHOLDS,
    EVENT_BOOL_COLUMNS,
    EVENT_NUMERIC_COLUMNS,
    EVENT_OUTPUT_COLUMNS,
    SQLITE_COLUMN_TYPES,
    EventThresholds,
)

DataLoader = Callable[[str, str, Optional[List[str]]], pd.DataFrame]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_value(name: str, fallback: Any) -> Any:
    try:
        from config.config import Config

        return getattr(Config, name, fallback) or fallback
    except Exception:
        return fallback


def _normalize_symbols(symbols: Optional[Iterable[str]]) -> Optional[List[str]]:
    if symbols is None:
        return None
    result: List[str] = []
    for symbol in symbols:
        text = str(symbol).strip()
        if not text:
            continue
        result.append(text)
        if "." in text:
            result.append(text.split(".", 1)[0])
    return sorted(set(result))


def _date_minus_calendar_days(date_text: str, days: int) -> str:
    date_value = datetime.strptime(str(date_text)[:10], "%Y-%m-%d")
    return (date_value - timedelta(days=days)).strftime("%Y-%m-%d")


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value
    return value


class DailyEventTagStore:
    """SQLite-backed store for generated daily event tags."""

    TABLE_NAME = "daily_event_tags"

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        thresholds: EventThresholds = DEFAULT_THRESHOLDS,
    ) -> None:
        default_db = _project_root() / "data" / "database" / "stock_data.db"
        self.db_path = Path(db_path or _config_value("DB_PATH", default_db))
        self.thresholds = thresholds

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
        columns_sql = ",\n                ".join(
            f"{column} {SQLITE_COLUMN_TYPES[column]}" for column in EVENT_OUTPUT_COLUMNS
        )
        with self._connection() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    {columns_sql},
                    created_at TEXT,
                    PRIMARY KEY (stock_code, trade_date)
                )
                """
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_date ON {self.TABLE_NAME}(trade_date)"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_symbol_date ON {self.TABLE_NAME}(stock_code, trade_date)"
            )

    def load_source_data(self, start_date: str, end_date: str, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """Load daily source rows from existing Parquet files using Polars."""
        try:
            import polars as pl
        except ImportError as exc:
            raise RuntimeError("polars is required to generate event tags from Parquet data") from exc

        parquet_dir = Path(_config_value("PARQUET_DIR", _project_root() / "data" / "parquet_data"))
        daily_path = parquet_dir / "stock_daily.parquet"
        info_path = parquet_dir / "stock_info.parquet"
        limit_path = parquet_dir / "stock_limit_status.parquet"

        if not daily_path.exists():
            raise FileNotFoundError(f"stock_daily.parquet not found: {daily_path}")

        wanted_daily_columns = [
            "stock_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "prev_close",
            "change_pct",
            "volume",
            "amount",
            "total_mv",
            "turnover_rate",
            "limit_up",
            "limit_down",
            "ma5",
            "ma10",
            "volume_ma5",
        ]

        daily_lazy = pl.scan_parquet(str(daily_path))
        daily_schema = daily_lazy.collect_schema().names()
        daily_columns = [col for col in wanted_daily_columns if col in daily_schema]
        daily_lazy = daily_lazy.filter(
            (pl.col("trade_date") >= start_date) & (pl.col("trade_date") <= end_date)
        )

        normalized_symbols = _normalize_symbols(symbols)
        if normalized_symbols:
            daily_lazy = daily_lazy.filter(pl.col("stock_code").is_in(normalized_symbols))

        daily_lazy = daily_lazy.select(daily_columns)

        if info_path.exists():
            info_lazy = pl.scan_parquet(str(info_path))
            info_schema = info_lazy.collect_schema().names()
            info_columns = [col for col in ["stock_code", "stock_name", "is_st", "is_kc", "is_cy"] if col in info_schema]
            if "stock_code" in info_columns:
                daily_lazy = daily_lazy.join(info_lazy.select(info_columns), on="stock_code", how="left")

        if limit_path.exists():
            limit_lazy = pl.scan_parquet(str(limit_path))
            limit_schema = limit_lazy.collect_schema().names()
            limit_columns = [
                col
                for col in ["stock_code", "trade_date", "is_limit_up", "is_limit_down", "is_opened", "is_suspended"]
                if col in limit_schema
            ]
            if {"stock_code", "trade_date"}.issubset(set(limit_columns)):
                limit_lazy = limit_lazy.filter(
                    (pl.col("trade_date") >= start_date) & (pl.col("trade_date") <= end_date)
                ).select(limit_columns)
                daily_lazy = daily_lazy.join(limit_lazy, on=["stock_code", "trade_date"], how="left")

        return daily_lazy.collect().to_pandas()

    def upsert_tags(self, tags: pd.DataFrame) -> int:
        self.ensure_table()
        if tags is None or tags.empty:
            return 0

        columns = [column for column in EVENT_OUTPUT_COLUMNS + ["created_at"] if column in tags.columns]
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        update_columns = [column for column in columns if column not in {"stock_code", "trade_date"}]
        update_sql = ", ".join(f"{column}=excluded.{column}" for column in update_columns)

        rows = []
        for record in tags[columns].to_dict("records"):
            cleaned = []
            for column in columns:
                value = record.get(column)
                if column in EVENT_BOOL_COLUMNS:
                    value = int(bool(value))
                cleaned.append(_clean_value(value))
            rows.append(tuple(cleaned))

        with self._connection() as conn:
            conn.executemany(
                f"""
                INSERT INTO {self.TABLE_NAME} ({column_sql})
                VALUES ({placeholders})
                ON CONFLICT(stock_code, trade_date) DO UPDATE SET
                    {update_sql}
                """,
                rows,
            )
        return len(rows)

    def generate_daily_event_tags(
        self,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
        data_loader: Optional[DataLoader] = None,
    ) -> Dict[str, Any]:
        read_start = _date_minus_calendar_days(start_date, self.thresholds.lookback_calendar_days)
        normalized_symbols = _normalize_symbols(symbols)
        loader = data_loader or self.load_source_data
        source_df = loader(read_start, end_date, normalized_symbols)
        tags = tag_daily_events(source_df, thresholds=self.thresholds)

        if not tags.empty:
            mask = (tags["trade_date"] >= start_date) & (tags["trade_date"] <= end_date)
            if normalized_symbols:
                mask = mask & tags["stock_code"].isin(normalized_symbols)
            tags = tags.loc[mask].copy()

        rows_stored = self.upsert_tags(tags)
        return {
            "success": True,
            "storage": "sqlite",
            "db_path": str(self.db_path),
            "table": self.TABLE_NAME,
            "start_date": start_date,
            "end_date": end_date,
            "symbols": normalized_symbols,
            "rows_source": int(len(source_df)) if source_df is not None else 0,
            "rows_generated": int(len(tags)),
            "rows_stored": int(rows_stored),
        }

    def query_event_tags(
        self,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        self.ensure_table()
        normalized_symbols = _normalize_symbols(symbols)

        where = ["trade_date >= ?", "trade_date <= ?"]
        params: List[Any] = [start_date, end_date]

        if normalized_symbols:
            placeholders = ", ".join(["?"] * len(normalized_symbols))
            where.append(f"stock_code IN ({placeholders})")
            params.extend(normalized_symbols)

        self._append_filters(where, params, filters or {})
        params.append(max(1, min(int(limit), 20000)))

        sql = f"""
            SELECT *
            FROM {self.TABLE_NAME}
            WHERE {" AND ".join(where)}
            ORDER BY trade_date ASC, stock_code ASC
            LIMIT ?
        """
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def _append_filters(self, where: List[str], params: List[Any], filters: Dict[str, Any]) -> None:
        allowed = set(EVENT_OUTPUT_COLUMNS)
        numeric_allowed = set(EVENT_NUMERIC_COLUMNS) | {
            "change_pct",
            "volume",
            "amount",
            "total_mv",
            "turnover_rate",
            "distance_to_ma5",
            "distance_to_20d_high",
        }

        for key, value in filters.items():
            if value is None or value == "":
                continue
            if key == "match_any" and isinstance(value, list):
                event_columns = [col for col in value if col in EVENT_BOOL_COLUMNS]
                if event_columns:
                    where.append("(" + " OR ".join(f"{col} = 1" for col in event_columns) + ")")
                continue
            if key.endswith("__gte"):
                column = key[:-5]
                if column in numeric_allowed:
                    where.append(f"{column} >= ?")
                    params.append(value)
                continue
            if key.endswith("__lte"):
                column = key[:-5]
                if column in numeric_allowed:
                    where.append(f"{column} <= ?")
                    params.append(value)
                continue
            if key not in allowed:
                continue
            if key in EVENT_BOOL_COLUMNS:
                where.append(f"{key} = ?")
                params.append(1 if bool(value) else 0)
            elif isinstance(value, dict):
                if "min" in value:
                    where.append(f"{key} >= ?")
                    params.append(value["min"])
                if "max" in value:
                    where.append(f"{key} <= ?")
                    params.append(value["max"])
            else:
                where.append(f"{key} = ?")
                params.append(value)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        for column in EVENT_BOOL_COLUMNS:
            if column in result:
                result[column] = bool(result[column])
        return result


def generate_daily_event_tags(
    start_date: str,
    end_date: str,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return DailyEventTagStore().generate_daily_event_tags(start_date, end_date, symbols)


def query_event_tags(
    start_date: str,
    end_date: str,
    symbols: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    return DailyEventTagStore().query_event_tags(start_date, end_date, symbols, filters)
