"""
Unified data query adapter for LanceDB.

The compatibility methods still return Pandas DataFrames, but hot paths can
now call the Polars/Arrow variants and avoid materializing data into Pandas.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set
import time

import pandas as pd
import polars as pl
import pyarrow as pa
from loguru import logger

try:
    from data_svc.storage.lancedb_reader import LanceDBDataReader, get_lancedb_reader

    LANCEDB_AVAILABLE = True
except ImportError:
    LanceDBDataReader = object  # type: ignore
    LANCEDB_AVAILABLE = False


PROJECT_ROOT = Path(__file__).parent.parent

_stock_basic_polars_cache: Optional[pl.DataFrame] = None
_fund_basic_cache = None
_libraries_cache: Optional[Set[str]] = None
_symbols_cache = {}
_cache_timestamp = 0.0
_CACHE_TTL = 300


def _invalidate_cache_if_needed() -> None:
    global _libraries_cache, _symbols_cache, _cache_timestamp
    current_time = time.time()
    if current_time - _cache_timestamp > _CACHE_TTL:
        _libraries_cache = None
        _symbols_cache = {}
        _cache_timestamp = current_time


def get_libraries_cached() -> Set[str]:
    global _libraries_cache
    _invalidate_cache_if_needed()

    if _libraries_cache is None:
        lancedb_path = PROJECT_ROOT / "data" / "lancedb"
        if lancedb_path.exists():
            _libraries_cache = {d.name for d in lancedb_path.iterdir() if d.is_dir()}
        else:
            _libraries_cache = set()
    return _libraries_cache


def _convert_to_polars(data) -> pl.DataFrame:
    if data is None:
        return pl.DataFrame()
    if isinstance(data, pl.DataFrame):
        return data
    if hasattr(data, "to_polars"):
        return data.to_polars()
    if hasattr(data, "to_arrow"):
        return pl.from_arrow(data.to_arrow())
    if isinstance(data, pd.DataFrame):
        return pl.from_pandas(data)
    return pl.DataFrame(data)


def _to_pandas_compat(df: pl.DataFrame) -> pd.DataFrame:
    """Convert only at API compatibility boundaries."""
    if df.is_empty():
        return pd.DataFrame()
    try:
        return df.to_pandas(use_pyarrow_extension_array=True)
    except TypeError:
        return df.to_pandas()


class UnifiedDataQuery:
    """Unified read facade with Pandas-compatible and columnar return paths."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(PROJECT_ROOT / "data" / "lancedb")
        self._reader = None

    @property
    def reader(self) -> Optional[LanceDBDataReader]:
        if self._reader is None and LANCEDB_AVAILABLE:
            self._reader = get_lancedb_reader(self.db_path)
        return self._reader

    def get_stock_history(
        self,
        symbol: str,
        start: str,
        end: str,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        return _to_pandas_compat(self.get_stock_history_polars(symbol, start, end, columns))

    def get_stock_history_polars(
        self,
        symbol: str,
        start: str,
        end: str,
        columns: Optional[List[str]] = None,
    ) -> pl.DataFrame:
        return self._read_polars(symbol, start, end, columns=columns, table_name="daily_ohlcv")

    def get_stock_history_arrow(
        self,
        symbol: str,
        start: str,
        end: str,
        columns: Optional[List[str]] = None,
    ) -> pa.Table:
        return self.get_stock_history_polars(symbol, start, end, columns).to_arrow()

    def get_stock_basic(self) -> pd.DataFrame:
        return _to_pandas_compat(self.get_stock_basic_polars())

    def get_stock_basic_polars(self) -> pl.DataFrame:
        global _stock_basic_polars_cache

        if _stock_basic_polars_cache is not None:
            return _stock_basic_polars_cache.clone()

        df = self._read_polars(None, "1900-01-01", "2100-12-31", table_name="stock_info")
        if not df.is_empty():
            _stock_basic_polars_cache = df.clone()
        return df

    def get_index_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        return _to_pandas_compat(self.get_index_daily_polars(symbol, start, end))

    def get_index_daily_polars(self, symbol: str, start: str, end: str) -> pl.DataFrame:
        return self._read_polars(symbol, start, end, table_name="index_daily")

    def get_fund_nav(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        return _to_pandas_compat(self.get_fund_nav_polars(symbol, start, end))

    def get_fund_nav_polars(self, symbol: str, start: str, end: str) -> pl.DataFrame:
        return self._read_polars(symbol, start, end, table_name="fund_nav")

    def _read_polars(
        self,
        symbol: Optional[str],
        start: Optional[str],
        end: Optional[str],
        columns: Optional[List[str]] = None,
        table_name: str = "daily_ohlcv",
    ) -> pl.DataFrame:
        if not self.reader:
            logger.warning("[UnifiedDataQuery] LanceDB not available")
            return pl.DataFrame()

        try:
            if hasattr(self.reader, "read_table"):
                df = self.reader.read_table(table_name, symbol, start, end, fields=columns)
            else:
                df = self.reader.read(symbol, start, end, fields=columns)

            if df.is_empty():
                return pl.DataFrame()
            if columns:
                available_cols = [c for c in columns if c in df.columns]
                df = df.select(available_cols)
            return df
        except Exception as exc:
            logger.warning("[UnifiedDataQuery] read error table={} symbol={}: {}", table_name, symbol, exc)
            return pl.DataFrame()

    def get_trade_dates(self, start: str, end: str) -> List[str]:
        if not self.reader:
            return []

        try:
            if hasattr(self.reader, "read_table"):
                df = self.reader.read_table("daily_ohlcv", None, start, end, fields=["trade_date"])
            else:
                df = self.reader.read_all(start, end, fields=["trade_date"])
            if df.is_empty() or "trade_date" not in df.columns:
                return []
            dates = df["trade_date"].unique().sort().to_list()
            return [str(d)[:10] for d in dates]
        except Exception as exc:
            logger.warning("[UnifiedDataQuery] trade_dates error: {}", exc)
            return []

    def list_symbols(self, table_name: str = "daily_ohlcv") -> List[str]:
        if not self.reader:
            return []

        try:
            try:
                return self.reader.list_symbols(table_name)
            except TypeError:
                return self.reader.list_symbols()
        except Exception as exc:
            logger.warning("[UnifiedDataQuery] list_symbols error: {}", exc)
            return []


_unified_data_query_instance: Optional[UnifiedDataQuery] = None


def get_unified_data_query(db_path: Optional[str] = None) -> UnifiedDataQuery:
    global _unified_data_query_instance
    if _unified_data_query_instance is None:
        _unified_data_query_instance = UnifiedDataQuery(db_path)
    return _unified_data_query_instance


def reset_unified_data_query() -> None:
    global _unified_data_query_instance, _stock_basic_polars_cache, _fund_basic_cache
    _unified_data_query_instance = None
    _stock_basic_polars_cache = None
    _fund_basic_cache = None
