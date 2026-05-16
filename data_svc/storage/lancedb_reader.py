"""
LanceDB read layer.

The hot path keeps data columnar as long as possible:
Lance scanner -> Arrow Table -> Polars DataFrame. Compatibility helpers that
return Python lists, dictionaries, NumPy arrays, or Pandas objects are kept at
the boundary where callers explicitly need them.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import hashlib
import json
import threading
import time

import numpy as np
import polars as pl
import pyarrow as pa
from loguru import logger

try:
    import lancedb

    LANCEDB_AVAILABLE = True
except ImportError:
    lancedb = None
    LANCEDB_AVAILABLE = False


DEFAULT_OHLCV_COLUMNS = [
    "stock_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]

MINIMAL_BACKTEST_COLUMNS = [
    "stock_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adj_factor",
    "prev_close",
    "total_mv",
    "limit_up",
    "limit_down",
]


class LanceDBDataReader:
    """Unified LanceDB reader with per-table scanner caching."""

    TABLE_NAME = "daily_ohlcv"

    def __init__(self, db_path: Optional[str] = None):
        if not LANCEDB_AVAILABLE:
            raise ImportError("LanceDB is required. Install with: pip install lancedb")

        if db_path is None:
            from config.config import Config

            db_path = getattr(Config, "LANCEDB_PATH", None)
            if db_path is None:
                project_root = Path(__file__).parent.parent.parent
                db_path = str(project_root / "data" / "lancedb")

        self.db_path = db_path
        self._db = None
        self._table = None
        self._lance_ds = None
        self._schema_columns = None
        self._tables: Dict[str, Any] = {}
        self._datasets: Dict[str, Any] = {}
        self._schema_columns_by_table: Dict[str, set] = {}

        self._memory_cache: OrderedDict[str, pl.DataFrame] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._max_cache_size_mb = 2048
        self._current_cache_size_mb = 0.0

        self._query_count = 0
        self._cache_hits = 0

    def _connect(self) -> None:
        if self._db is None:
            self._db = lancedb.connect(self.db_path)

    @property
    def table(self):
        self._table = self._get_table(self.TABLE_NAME)
        return self._table

    @property
    def lance_ds(self):
        self._lance_ds = self._get_dataset(self.TABLE_NAME)
        return self._lance_ds

    @property
    def library(self):
        return self.table

    def _get_table(self, table_name: str):
        if table_name not in self._tables:
            self._connect()
            self._tables[table_name] = (
                self._db.open_table(table_name) if table_name in self._db.table_names() else None
            )
        return self._tables[table_name]

    def _get_dataset(self, table_name: str):
        if table_name not in self._datasets:
            table = self._get_table(table_name)
            if table is None:
                self._datasets[table_name] = None
            else:
                try:
                    self._datasets[table_name] = table.to_lance()
                except ImportError:
                    self._datasets[table_name] = table
        return self._datasets[table_name]

    def _get_schema_columns(self, table_name: str = TABLE_NAME) -> set:
        if table_name not in self._schema_columns_by_table:
            table = self._get_table(table_name)
            self._schema_columns_by_table[table_name] = (
                {field.name for field in table.schema} if table is not None else set()
            )
        if table_name == self.TABLE_NAME:
            self._schema_columns = self._schema_columns_by_table[table_name]
        return self._schema_columns_by_table[table_name]

    def _normalize_fields(self, fields: Optional[List[str]], table_name: str = TABLE_NAME) -> Optional[List[str]]:
        if fields is None:
            return None
        schema_columns = self._get_schema_columns(table_name)
        if not schema_columns:
            return fields
        normalized = [field for field in fields if field in schema_columns]
        missing = sorted(set(fields) - set(normalized))
        if missing:
            logger.debug(f"[LanceDBDataReader] skip missing columns from {table_name}: {missing}")
        return normalized

    def _estimate_size_mb(self, df: pl.DataFrame) -> float:
        if df is None or df.is_empty():
            return 0.0
        return df.estimated_size() / (1024 * 1024)

    def _evict_lru(self, needed_mb: float) -> None:
        while self._current_cache_size_mb + needed_mb > self._max_cache_size_mb and self._memory_cache:
            _, oldest_df = self._memory_cache.popitem(last=False)
            self._current_cache_size_mb -= self._estimate_size_mb(oldest_df)
        if self._current_cache_size_mb < 0:
            self._current_cache_size_mb = 0.0

    def set_cache_limit(self, max_size_mb: int) -> None:
        with self._cache_lock:
            self._max_cache_size_mb = max_size_mb
            self._evict_lru(0)

    def get_cache_size_mb(self) -> float:
        with self._cache_lock:
            return self._current_cache_size_mb

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._memory_cache.clear()
            self._current_cache_size_mb = 0.0

    def _make_cache_key(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str],
        end_date: Optional[str],
        fields: Optional[List[str]] = None,
        table_name: str = TABLE_NAME,
    ) -> str:
        if symbols is None:
            symbols_key: Union[str, Tuple[str, ...]] = "all"
        elif isinstance(symbols, str):
            symbols_key = symbols
        else:
            symbols_key = tuple(symbols)

        key_data = {
            "table": table_name,
            "symbols": symbols_key,
            "start_date": start_date or "min",
            "end_date": end_date or "max",
            "fields": tuple(sorted(fields)) if fields else "all",
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _build_filters(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[str]:
        filters = []
        if start_date:
            filters.append(f"trade_date >= date '{start_date}'")
        if end_date:
            filters.append(f"trade_date <= date '{end_date}'")
        if symbols is not None:
            if isinstance(symbols, str):
                filters.append(f"stock_code = '{symbols}'")
            elif len(symbols) == 1:
                filters.append(f"stock_code = '{symbols[0]}'")
            elif len(symbols) <= 100:
                quoted = [f"'{s}'" for s in symbols]
                filters.append(f"stock_code IN ({', '.join(quoted)})")
        return filters

    def _apply_filters_polars(self, df: pl.DataFrame, filters: List[str]) -> pl.DataFrame:
        for filter_text in filters:
            if "trade_date >=" in filter_text:
                start_date = filter_text.split("'")[1]
                df = df.filter(pl.col("trade_date") >= pl.lit(start_date).str.to_date())
            elif "trade_date <=" in filter_text:
                end_date = filter_text.split("'")[1]
                df = df.filter(pl.col("trade_date") <= pl.lit(end_date).str.to_date())
            elif "stock_code =" in filter_text:
                code = filter_text.split("'")[1]
                df = df.filter(pl.col("stock_code") == code)
            elif "stock_code IN" in filter_text:
                codes_str = filter_text.split("(")[1].rstrip(")")
                codes = [c.strip().strip("'") for c in codes_str.split(",")]
                df = df.filter(pl.col("stock_code").is_in(codes))
        return df

    def read(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        as_of: Optional[datetime] = None,
        table_name: str = TABLE_NAME,
    ) -> pl.DataFrame:
        return self.read_table(table_name, symbols, start_date, end_date, fields=fields, as_of=as_of)

    def read_table(
        self,
        table_name: str,
        symbols: Union[str, List[str], None],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        as_of: Optional[datetime] = None,
    ) -> pl.DataFrame:
        dataset = self._get_dataset(table_name)
        if dataset is None:
            logger.warning(f"[LanceDBDataReader] table not found: {table_name}")
            return pl.DataFrame()

        self._query_count += 1
        if fields is None:
            fields = DEFAULT_OHLCV_COLUMNS if table_name == self.TABLE_NAME else None
        fields = self._normalize_fields(fields, table_name)
        if fields == []:
            logger.warning(f"[LanceDBDataReader] no requested fields exist in schema: {table_name}")
            return pl.DataFrame()

        cache_key = self._make_cache_key(symbols, start_date, end_date, fields, table_name=table_name)
        with self._cache_lock:
            cached = self._memory_cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                self._memory_cache.move_to_end(cache_key)
                return cached.clone()

        t0 = time.perf_counter()
        try:
            filters = self._build_filters(symbols, start_date, end_date)
            scanner_kwargs: Dict[str, Any] = {}
            if fields:
                scanner_kwargs["columns"] = fields
            if filters:
                scanner_kwargs["filter"] = " AND ".join(filters)

            if hasattr(dataset, "scanner"):
                arrow_table = dataset.scanner(**scanner_kwargs).to_table()
            else:
                table = self._get_table(table_name)
                arrow_table = table.to_arrow()

            df = pl.from_arrow(arrow_table)
            if filters and not hasattr(dataset, "scanner"):
                df = self._apply_filters_polars(df, filters)

            read_time = time.perf_counter() - t0
            logger.debug(f"[LanceDBDataReader] read {table_name}: rows={len(df)} elapsed={read_time:.2f}s")

            if not df.is_empty():
                size_mb = self._estimate_size_mb(df)
                if size_mb <= self._max_cache_size_mb * 0.25:
                    with self._cache_lock:
                        self._evict_lru(size_mb)
                        self._memory_cache[cache_key] = df.clone()
                        self._current_cache_size_mb += size_mb
                else:
                    logger.debug(f"[LanceDBDataReader] skip caching large result: {size_mb:.1f}MB")
            return df
        except Exception as exc:
            logger.error(f"[LanceDBDataReader] read failed table={table_name}: {exc}")
            return pl.DataFrame()

    def read_arrow(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        table_name: str = TABLE_NAME,
    ) -> pa.Table:
        df = self.read_table(table_name, symbols, start_date, end_date, fields=fields)
        return df.to_arrow()

    def read_all_columns(
        self,
        symbols: Union[str, List[str], None] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        table_name: str = TABLE_NAME,
    ) -> pl.DataFrame:
        return self.read_table(table_name, symbols, start_date, end_date, fields=None)

    def read_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        return self.read(symbol, start_date, end_date)

    def read_batch(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        if not symbols:
            return pl.DataFrame()
        if len(symbols) > 100:
            all_dfs = []
            for i in range(0, len(symbols), 100):
                df = self.read(symbols[i : i + 100], start_date, end_date)
                if not df.is_empty():
                    all_dfs.append(df)
            return pl.concat(all_dfs) if all_dfs else pl.DataFrame()
        return self.read(symbols, start_date, end_date)

    def read_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        table_name: str = TABLE_NAME,
    ) -> pl.DataFrame:
        if fields is None and table_name == self.TABLE_NAME:
            fields = MINIMAL_BACKTEST_COLUMNS
        return self.read_table(table_name, None, start_date, end_date, fields=fields)

    def get_db_stats(self) -> Dict[str, Any]:
        try:
            dataset = self._get_dataset(self.TABLE_NAME)
            if dataset is None:
                return {"row_count": 0, "latest_date": None, "stock_count": 0, "oldest_date": None}

            import duckdb

            scanner = dataset.scanner(columns=["trade_date", "stock_code"])
            arrow_table = scanner.to_table()
            conn = duckdb.connect(database=":memory:")
            conn.register("dailies", arrow_table)
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as row_count,
                    MAX(trade_date) as latest_date,
                    MIN(trade_date) as oldest_date,
                    COUNT(DISTINCT stock_code) as stock_count
                FROM dailies
                """
            ).fetchone()
            conn.close()
            return {
                "row_count": row[0] or 0,
                "latest_date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "oldest_date": row[2].strftime("%Y-%m-%d") if row[2] else None,
                "stock_count": row[3] or 0,
            }
        except Exception as exc:
            logger.warning(f"[LanceDBDataReader] get_db_stats failed: {exc}")
            return {"row_count": 0, "latest_date": None, "stock_count": 0, "oldest_date": None}

    def read_as_dict(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        filter_stocks: Optional[set] = None,
        date_field: str = "trade_date",
        code_field: str = "stock_code",
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Compatibility API that materializes NumPy arrays by stock."""
        if fields is None:
            fields = list(DEFAULT_OHLCV_COLUMNS)
        fields = list(dict.fromkeys([date_field, code_field, *fields]))

        df = self.read(None, start_date, end_date, fields=fields)
        if df.is_empty():
            return {}
        if filter_stocks:
            df = df.filter(~pl.col(code_field).is_in(filter_stocks))

        df = df.sort([code_field, date_field])
        result: Dict[str, Dict[str, np.ndarray]] = {}
        for key, group in df.partition_by(code_field, as_dict=True, maintain_order=True).items():
            code = key[0] if isinstance(key, tuple) else key
            result[code] = {
                col: group[col].to_numpy()
                for col in group.columns
                if col != code_field
            }

        logger.debug(f"[LanceDBDataReader] read_as_dict returned {len(result)} symbols")
        return result

    def get_latest(self, symbols: Optional[List[str]] = None, n: int = 1) -> pl.DataFrame:
        df = self.read(symbols)
        if df.is_empty():
            return pl.DataFrame()
        if "trade_date" in df.columns:
            df = df.sort("trade_date", descending=True).head(n)
        return df

    def list_symbols(self, table_name: str = TABLE_NAME) -> List[str]:
        dataset = self._get_dataset(table_name)
        if dataset is None:
            return []
        try:
            import duckdb

            arrow_table = dataset.scanner(columns=["stock_code"]).to_table()
            conn = duckdb.connect(database=":memory:")
            conn.register("symbols", arrow_table)
            rows = conn.execute("SELECT DISTINCT stock_code FROM symbols ORDER BY stock_code").fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as exc:
            logger.warning(f"[LanceDBDataReader] list_symbols DuckDB fallback: {exc}")
            try:
                arrow_table = dataset.scanner(columns=["stock_code"]).to_table()
                codes = arrow_table.column("stock_code").to_pylist()
                return sorted(set(codes))
            except Exception as inner_exc:
                logger.error(f"[LanceDBDataReader] list_symbols failed: {inner_exc}")
                return []

    def list_dates(self, table_name: str = TABLE_NAME) -> List[str]:
        dataset = self._get_dataset(table_name)
        if dataset is None:
            return []
        try:
            import duckdb

            arrow_table = dataset.scanner(columns=["trade_date"]).to_table()
            conn = duckdb.connect(database=":memory:")
            conn.register("dailies", arrow_table)
            rows = conn.execute(
                "SELECT DISTINCT trade_date FROM dailies ORDER BY trade_date DESC"
            ).fetchall()
            conn.close()
            return [str(row[0])[:10] for row in rows]
        except Exception as exc:
            logger.error(f"[LanceDBDataReader] list_dates failed: {exc}")
            return []

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        dates = self.list_dates()
        if not dates:
            return None, None
        return dates[-1], dates[0]

    def preload(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        logger.info(f"[LanceDBDataReader] preload {start_date} ~ {end_date}")
        t0 = time.perf_counter()
        df = self.read_all(start_date, end_date)
        elapsed = time.perf_counter() - t0
        logger.info(
            f"[LanceDBDataReader] preload done rows={len(df)} elapsed={elapsed:.2f}s "
            f"cache={self._current_cache_size_mb:.1f}MB"
        )
        return df

    def get_stats(self) -> Dict[str, Any]:
        return {
            "query_count": self._query_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / max(1, self._query_count),
            "cache_size_mb": self._current_cache_size_mb,
            "cache_entries": len(self._memory_cache),
        }

    def query_with_duckdb(
        self,
        sql: str,
        stock_list: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        try:
            import duckdb
        except ImportError:
            logger.warning("[LanceDBDataReader] DuckDB not available")
            return pl.DataFrame()

        dataset = self._get_dataset(self.TABLE_NAME)
        if dataset is None:
            return pl.DataFrame()

        try:
            filters = []
            if stock_list and len(stock_list) <= 100:
                quoted = [f"'{s}'" for s in stock_list]
                filters.append(f"stock_code IN ({', '.join(quoted)})")
            if start_date:
                filters.append(f"trade_date >= date '{start_date}'")
            if end_date:
                filters.append(f"trade_date <= date '{end_date}'")

            scanner_kwargs = {"filter": " AND ".join(filters)} if filters else {}
            arrow_table = dataset.scanner(**scanner_kwargs).to_table()
            full_sql = sql.replace("lance_table", "arrow_table")

            conn = duckdb.connect(database=":memory:")
            conn.register("arrow_table", arrow_table)
            result = conn.execute(full_sql).pl()
            conn.close()
            return result
        except Exception as exc:
            logger.error(f"[LanceDBDataReader] DuckDB query failed: {exc}")
            return pl.DataFrame()

    def get_stock_direction_stats(
        self,
        window_size: int = 20,
        threshold_pct: float = 0.02,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        sql = """
        SELECT
            stock_code,
            COUNT(*) as n_rows,
            FIRST(close ORDER BY trade_date) as first_close,
            LAST(close ORDER BY trade_date) as last_close
        FROM arrow_table
        GROUP BY stock_code
        """
        return self.query_with_duckdb(sql, start_date=start_date, end_date=end_date)

    def close(self) -> None:
        self._db = None
        self._table = None
        self._lance_ds = None
        self._tables.clear()
        self._datasets.clear()
        self._schema_columns_by_table.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


_reader_instance: Optional[LanceDBDataReader] = None
_reader_lock = threading.Lock()


def get_lancedb_reader(db_path: Optional[str] = None) -> LanceDBDataReader:
    global _reader_instance
    if _reader_instance is None:
        with _reader_lock:
            if _reader_instance is None:
                _reader_instance = LanceDBDataReader(db_path)
    return _reader_instance
