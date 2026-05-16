"""
Memory-mapped Arrow IPC cache for hot tabular data.

The service keeps the existing public API (`write_mmap`, `read_mmap`,
`MmapDataLoader`) but stores data as a standard Arrow IPC file. Reads use
`pyarrow.memory_map`, so Arrow can reference file-backed buffers instead of
copying the whole file into Python bytes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl
import pyarrow as pa
import pyarrow.ipc as ipc

from config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MMAPStats:
    """Runtime stats for one memory-mapped table."""

    file_path: str
    file_size_mb: float
    num_rows: int
    num_columns: int
    columns: List[str]
    read_count: int
    total_read_time_ms: float
    cache_hit_count: int


class MemoryMapService:
    """File-backed Arrow cache with Polars-friendly reads."""

    SCHEMA_VERSION = 2

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent
            cache_dir = str(project_root / "data" / "mmap_cache")

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._stats: Dict[str, MMAPStats] = {}

        logger.info("[MemoryMapService] initialized: %s", self.cache_dir)

    def _get_cache_path(self, table_name: str) -> Path:
        return self.cache_dir / f"{table_name}.arrow"

    def _get_legacy_cache_path(self, table_name: str) -> Path:
        return self.cache_dir / f"{table_name}.mmap"

    def _get_meta_path(self, table_name: str) -> Path:
        return self.cache_dir / f"{table_name}.meta"

    def write_mmap(self, df: pl.DataFrame, table_name: str = "daily_ohlcv") -> bool:
        """Write a Polars DataFrame as a memory-mappable Arrow IPC file."""
        try:
            start_time = time.perf_counter()
            mmap_path = self._get_cache_path(table_name)
            meta_path = self._get_meta_path(table_name)

            sort_cols = [c for c in ("stock_code", "trade_date") if c in df.columns]
            if sort_cols:
                df = df.sort(sort_cols)

            arrow_table = df.to_arrow()
            tmp_path = mmap_path.with_suffix(".arrow.tmp")

            with pa.OSFile(str(tmp_path), "wb") as sink:
                with ipc.new_file(sink, arrow_table.schema) as writer:
                    writer.write_table(arrow_table)
            tmp_path.replace(mmap_path)

            meta_info = {
                "format": "arrow-ipc-file",
                "schema_version": self.SCHEMA_VERSION,
                "columns": list(df.columns),
                "dtypes": [str(df[col].dtype) for col in df.columns],
                "num_rows": len(df),
                "num_cols": len(df.columns),
                "created_at": datetime.now().isoformat(),
            }
            meta_path.write_text(json.dumps(meta_info, ensure_ascii=False), encoding="utf-8")

            legacy_path = self._get_legacy_cache_path(table_name)
            if legacy_path.exists():
                logger.debug("[MemoryMapService] legacy mmap cache left untouched: %s", legacy_path)

            file_size_mb = mmap_path.stat().st_size / (1024 * 1024)
            self._stats[table_name] = MMAPStats(
                file_path=str(mmap_path),
                file_size_mb=file_size_mb,
                num_rows=len(df),
                num_columns=len(df.columns),
                columns=list(df.columns),
                read_count=0,
                total_read_time_ms=0.0,
                cache_hit_count=0,
            )

            elapsed = time.perf_counter() - start_time
            logger.info(
                "[MemoryMapService] wrote %s: rows=%s cols=%s size=%.1fMB elapsed=%.2fs",
                table_name,
                len(df),
                len(df.columns),
                file_size_mb,
                elapsed,
            )
            return True
        except Exception as exc:
            logger.exception("[MemoryMapService] write failed for %s: %s", table_name, exc)
            return False

    def read_mmap(
        self,
        table_name: str = "daily_ohlcv",
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[pl.DataFrame]:
        """Read a memory-mapped Arrow IPC file into a Polars DataFrame."""
        t0 = time.perf_counter()

        try:
            mmap_path = self._get_cache_path(table_name)
            meta_path = self._get_meta_path(table_name)

            if not mmap_path.exists():
                logger.warning("[MemoryMapService] cache file not found: %s", mmap_path)
                return None
            if not meta_path.exists():
                logger.warning("[MemoryMapService] metadata file not found: %s", meta_path)
                return None

            meta_info = json.loads(meta_path.read_text(encoding="utf-8"))
            all_columns = meta_info.get("columns", [])
            selected_columns = all_columns if columns is None else [c for c in columns if c in all_columns]
            if not selected_columns:
                return pl.DataFrame()

            df = self._read_columns_mmap(mmap_path, selected_columns)
            if filters:
                df = self._apply_filters(df, filters)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            stats = self._stats.get(table_name)
            if stats is not None:
                stats.read_count += 1
                stats.total_read_time_ms += elapsed_ms

            logger.debug(
                "[MemoryMapService] read %s: rows=%s cols=%s elapsed=%.1fms",
                table_name,
                len(df),
                len(df.columns),
                elapsed_ms,
            )
            return df
        except Exception as exc:
            logger.exception("[MemoryMapService] read failed for %s: %s", table_name, exc)
            return None

    def _read_columns_mmap(self, mmap_path: Path, columns: List[str]) -> pl.DataFrame:
        with pa.memory_map(str(mmap_path), "r") as source:
            table = ipc.open_file(source).read_all()

        if columns and columns != table.column_names:
            table = table.select(columns)
        return pl.from_arrow(table)

    def _apply_filters(self, df: pl.DataFrame, filters: Dict[str, Any]) -> pl.DataFrame:
        for col, value in filters.items():
            if col not in df.columns:
                continue
            if isinstance(value, (list, tuple)) and len(value) == 2:
                df = df.filter((pl.col(col) >= value[0]) & (pl.col(col) <= value[1]))
            else:
                df = df.filter(pl.col(col) == value)
        return df

    def exists(self, table_name: str) -> bool:
        return self._get_cache_path(table_name).exists() and self._get_meta_path(table_name).exists()

    def get_stats(self, table_name: str) -> Optional[MMAPStats]:
        return self._stats.get(table_name)

    def list_tables(self) -> List[str]:
        return sorted(f.stem for f in self.cache_dir.glob("*.meta"))

    def delete(self, table_name: str) -> bool:
        try:
            for path in (self._get_cache_path(table_name), self._get_meta_path(table_name)):
                if path.exists():
                    path.unlink()
            self._stats.pop(table_name, None)
            logger.info("[MemoryMapService] deleted %s", table_name)
            return True
        except Exception as exc:
            logger.exception("[MemoryMapService] delete failed for %s: %s", table_name, exc)
            return False

    def sync_from_lancedb(self, table_name: str = "daily_ohlcv", lancedb_path: Optional[str] = None) -> bool:
        """Build the mmap cache from a LanceDB table."""
        logger.info("[MemoryMapService] syncing from LanceDB: %s", table_name)
        try:
            if lancedb_path is None:
                from config.config import Config

                lancedb_path = getattr(Config, "LANCEDB_PATH", None)
                if lancedb_path is None:
                    project_root = Path(__file__).parent.parent.parent
                    lancedb_path = str(project_root / "data" / "lancedb")

            import lancedb

            db = lancedb.connect(lancedb_path)
            if table_name not in db.table_names():
                logger.error("[MemoryMapService] LanceDB table not found: %s", table_name)
                return False

            table = db.open_table(table_name)
            arrow_table = table.to_arrow()
            logger.info("[MemoryMapService] loaded LanceDB table %s: rows=%s", table_name, arrow_table.num_rows)
            return self.write_mmap(pl.from_arrow(arrow_table), table_name)
        except Exception as exc:
            logger.exception("[MemoryMapService] sync failed for %s: %s", table_name, exc)
            return False

    def close(self) -> None:
        logger.info("[MemoryMapService] closed")


class MmapDataLoader:
    """Convenience loader around MemoryMapService."""

    def __init__(self, db_path: Optional[str] = None):
        self.mmap_service = MemoryMapService()
        self.lancedb_path = db_path

    def ensure_mmap(self, table_name: str = "daily_ohlcv") -> bool:
        if not self.mmap_service.exists(table_name):
            logger.info("[MmapDataLoader] cache missing, creating: %s", table_name)
            return self.mmap_service.sync_from_lancedb(table_name, self.lancedb_path)
        return True

    def read(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        columns: Optional[List[str]] = None,
        table_name: str = "daily_ohlcv",
    ) -> pl.DataFrame:
        self.ensure_mmap(table_name)

        read_columns = list(columns) if columns else None
        for required_col in ("stock_code", "trade_date"):
            if read_columns is not None and required_col not in read_columns:
                read_columns.append(required_col)

        filters: Dict[str, Any] = {}
        if start_date:
            filters["trade_date"] = (start_date, end_date or "2099-12-31")
        elif end_date:
            filters["trade_date"] = ("1900-01-01", end_date)

        if isinstance(symbols, str):
            filters["stock_code"] = symbols

        df = self.mmap_service.read_mmap(table_name, read_columns, filters)
        if df is None or df.is_empty():
            return pl.DataFrame()

        if symbols and not isinstance(symbols, str):
            df = df.filter(pl.col("stock_code").is_in(symbols))

        if columns:
            df = df.select([c for c in columns if c in df.columns])
        return df


_global_mmap_service: Optional[MemoryMapService] = None


def get_mmap_service() -> MemoryMapService:
    global _global_mmap_service
    if _global_mmap_service is None:
        _global_mmap_service = MemoryMapService()
    return _global_mmap_service


def get_mmap_loader(db_path: Optional[str] = None) -> MmapDataLoader:
    return MmapDataLoader(db_path)
