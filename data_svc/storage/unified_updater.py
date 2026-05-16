"""Unified LanceDB data updater."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Optional

import lancedb
import pandas as pd
import polars as pl
from loguru import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config


@dataclass
class UpdateResult:
    success: bool
    message: str
    stock_dates_updated: int = 0
    stock_records_added: int = 0
    benchmark_dates_updated: int = 0
    benchmark_records_added: int = 0
    industry_records_updated: int = 0
    factor_records_computed: int = 0
    limit_status_records: int = 0
    errors: list[str] = field(default_factory=list)


class UnifiedDataUpdater:
    """Writes Tushare, DragonEye and factor outputs into LanceDB."""

    def __init__(self, progress_callback: Optional[Callable[[str, int, str], None]] = None):
        self.progress_callback = progress_callback
        self.token = Config.TUSHARE_TOKEN
        self.lancedb_path = getattr(Config, "LANCEDB_PATH", str(Path(BASE_DIR) / "data" / "lancedb"))

    def _emit_progress(self, status: str, progress: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(status, progress, message)
        logger.info("[UnifiedUpdater] {} {}% {}", status, progress, message)

    def _get_lancedb(self):
        Path(self.lancedb_path).mkdir(parents=True, exist_ok=True)
        return lancedb.connect(self.lancedb_path)

    def _get_latest_date(self, table_name: str) -> Optional[str]:
        try:
            db = self._get_lancedb()
            tables = self._list_tables(db)
            if table_name not in tables:
                return None
            df = pl.from_arrow(db.open_table(table_name).to_arrow())
            if df.is_empty() or "trade_date" not in df.columns:
                return None
            value = df.select(pl.col("trade_date").max()).item()
            if hasattr(value, "strftime"):
                return value.strftime("%Y%m%d")
            return str(value)[:10].replace("-", "")
        except Exception as exc:
            logger.warning("latest date lookup failed for {}: {}", table_name, exc)
            return None

    def _list_tables(self, db) -> list[str]:
        listed = db.list_tables()
        return listed.tables if hasattr(listed, "tables") else list(listed)

    def _get_trade_dates(self, pro, start_date: str, end_date: str) -> list[str]:
        cal_df = pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)
        if cal_df is None or cal_df.empty:
            return []
        return cal_df[cal_df["is_open"] == 1]["cal_date"].astype(str).tolist()

    def _delete_trade_dates(self, table, trade_dates: list[str]) -> None:
        for td in trade_dates:
            date_str = f"{td[:4]}-{td[4:6]}-{td[6:8]}" if len(str(td)) == 8 else str(td)[:10]
            try:
                table.delete(f"trade_date = DATE '{date_str}'")
            except Exception:
                try:
                    table.delete(f'trade_date = "{date_str}"')
                except Exception as exc:
                    logger.warning("delete date {} failed: {}", date_str, exc)

    def _add_or_create(self, table_name: str, df: pl.DataFrame, delete_dates: Optional[list[str]] = None) -> int:
        if df.is_empty():
            return 0
        db = self._get_lancedb()
        tables = self._list_tables(db)
        if table_name in tables:
            table = db.open_table(table_name)
            if delete_dates:
                self._delete_trade_dates(table, delete_dates)
            table.add(df.to_arrow())
        else:
            table = db.create_table(table_name, df.to_arrow())
            for col in ("trade_date", "stock_code", "symbol"):
                if col in df.columns:
                    try:
                        table.create_scalar_index(col)
                    except Exception:
                        pass
        return len(df)

    def update_stock_daily(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
        self._emit_progress("UPDATING", 10, "updating stock daily data")
        import tushare as ts

        pro = ts.pro_api(self.token)
        if start_date is None:
            latest = self._get_latest_date("daily_ohlcv")
            start_date = (datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d") if latest else "20200101"
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date > end_date:
            return {"dates_updated": 0, "records_added": 0}

        trade_dates = self._get_trade_dates(pro, start_date, end_date)
        frames: list[pd.DataFrame] = []
        for trade_date in trade_dates:
            df = pro.daily(trade_date=trade_date)
            if df is None or df.empty:
                continue
            daily_basic = pro.daily_basic(trade_date=trade_date)
            if daily_basic is not None and not daily_basic.empty:
                cols = [c for c in ["ts_code", "trade_date", "turnover_rate_f", "pe", "pe_ttm", "pb", "ps", "ps_ttm", "total_mv", "circ_mv"] if c in daily_basic.columns]
                keys = [c for c in ["ts_code", "trade_date"] if c in df.columns and c in daily_basic.columns]
                df = df.merge(daily_basic[cols], on=keys or ["ts_code"], how="left")
            adj = pro.adj_factor(trade_date=trade_date)
            if adj is not None and not adj.empty:
                cols = [c for c in ["ts_code", "trade_date", "adj_factor"] if c in adj.columns]
                keys = [c for c in ["ts_code", "trade_date"] if c in df.columns and c in adj.columns]
                df = df.merge(adj[cols], on=keys or ["ts_code"], how="left")
            df["stock_code"] = df["ts_code"]
            frames.append(df)

        if not frames:
            return {"dates_updated": 0, "records_added": 0}
        combined = pd.concat(frames, ignore_index=True)
        df_pl = pl.from_pandas(combined)
        rename_map = {
            "pct_chg": "change_pct",
            "vol": "volume",
            "turnover_rate_f": "turnover_rate",
            "pre_close": "prev_close",
            "change": "change_amount",
            "circ_mv": "float_mv",
        }
        df_pl = df_pl.rename({k: v for k, v in rename_map.items() if k in df_pl.columns})
        cols = [
            "stock_code", "trade_date", "open", "high", "low", "close", "volume", "amount",
            "change_pct", "change_amount", "prev_close", "turnover_rate", "total_mv", "float_mv",
            "pe", "pe_ttm", "pb", "ps", "ps_ttm", "adj_factor",
        ]
        df_pl = df_pl.select([c for c in cols if c in df_pl.columns])
        if "trade_date" not in df_pl.columns:
            raise ValueError("daily_ohlcv update produced no trade_date column")
        df_pl = df_pl.with_columns(pl.col("trade_date").cast(pl.Utf8).str.to_date("%Y%m%d"))
        fetched_dates = sorted(combined["trade_date"].dropna().astype(str).unique().tolist())
        rows = self._add_or_create("daily_ohlcv", df_pl, fetched_dates)
        return {"dates_updated": len(fetched_dates), "records_added": rows}

    def update_benchmark_daily(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
        self._emit_progress("UPDATING", 30, "updating benchmark index data")
        import tushare as ts

        pro = ts.pro_api(self.token)
        if start_date is None:
            latest = self._get_latest_date("index_daily")
            start_date = (datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d") if latest else "20200101"
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        indices = {
            "000300.SH": "CSI300",
            "000905.SH": "CSI500",
            "000001.SH": "SSE Composite",
            "399001.SZ": "SZSE Component",
            "000016.SH": "SSE50",
            "399006.SZ": "ChiNext",
        }
        frames = []
        for code, name in indices.items():
            df = pro.index_daily(ts_code=code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df["index_name"] = name
                frames.append(df)
        if not frames:
            return {"dates_updated": 0, "records_added": 0}
        combined = pd.concat(frames, ignore_index=True)
        df_pl = pl.from_pandas(combined).rename({"ts_code": "symbol", "vol": "volume", "index_name": "name"})
        cols = ["trade_date", "symbol", "name", "open", "high", "low", "close", "volume", "amount"]
        df_pl = df_pl.select([c for c in cols if c in df_pl.columns])
        df_pl = df_pl.with_columns(pl.col("trade_date").cast(pl.Utf8).str.to_date("%Y%m%d"))
        trade_dates = sorted(combined["trade_date"].dropna().astype(str).unique().tolist())
        rows = self._add_or_create("index_daily", df_pl, trade_dates)
        return {"dates_updated": len(trade_dates), "records_added": rows}

    def update_stock_basic(self) -> Dict[str, int]:
        self._emit_progress("UPDATING", 60, "updating stock_info snapshot")
        import tushare as ts

        pro = ts.pro_api(self.token)
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,market,list_date")
        if df is None or df.empty:
            return {"records_updated": 0}
        df["stock_code"] = df["ts_code"]
        df_pl = pl.from_pandas(df)
        db = self._get_lancedb()
        if "stock_info" in self._list_tables(db):
            db.drop_table("stock_info")
        db.create_table("stock_info", df_pl.to_arrow())
        return {"records_updated": len(df_pl)}

    def update_factors(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
        from data_svc.storage.factor_precompute_service import FactorPrecomputeService

        start_dash = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}" if start_date and len(start_date) == 8 else start_date
        end_dash = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}" if end_date and len(end_date) == 8 else end_date
        result = FactorPrecomputeService().precompute_all_factors(start_date=start_dash, end_date=end_dash)
        return {"factors_computed": result.records_computed if result.success else 0}

    def update_dragon_eye(self, target_date: Optional[str] = None) -> Dict[str, int]:
        self._emit_progress("UPDATING", 85, "updating DragonEye data")
        from data_svc.ingestion.dragon_eye_adapter import DragonEyeAdapter

        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        adapter = DragonEyeAdapter()
        if not adapter.crawl(target_date=target_date, backfill=False):
            return {"records_updated": 0}
        return {"records_updated": adapter.ingest_to_lancedb(target_date)}

    def run_full_update(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip_stock: bool = False,
        skip_benchmark: bool = False,
        skip_industry: bool = False,
        skip_factors: bool = False,
        skip_limit_status: bool = True,
        skip_dragon: bool = False,
    ) -> UpdateResult:
        started = time.time()
        result = UpdateResult(success=False, message="")
        try:
            if not skip_stock:
                stock = self.update_stock_daily(start_date, end_date)
                result.stock_dates_updated = stock.get("dates_updated", 0)
                result.stock_records_added = stock.get("records_added", 0)
                from data_svc.ingestion.gap_checker import check_and_repair_gaps

                repair_start = start_date
                if repair_start is None:
                    repair_start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
                repair_end = end_date or datetime.now().strftime("%Y%m%d")
                gap_repair = check_and_repair_gaps(
                    trading_dates=[
                        f"{repair_start[:4]}-{repair_start[4:6]}-{repair_start[6:8]}" if len(repair_start) == 8 else repair_start,
                        f"{repair_end[:4]}-{repair_end[4:6]}-{repair_end[6:8]}" if len(repair_end) == 8 else repair_end,
                    ],
                    auto_repair=True,
                )
                repaired_rows = sum(item.get("rows", 0) for item in gap_repair.get("repair_results", []))
                if repaired_rows:
                    result.stock_records_added += repaired_rows
            if not skip_benchmark:
                benchmark = self.update_benchmark_daily(start_date, end_date)
                result.benchmark_dates_updated = benchmark.get("dates_updated", 0)
                result.benchmark_records_added = benchmark.get("records_added", 0)
            if not skip_industry:
                basic = self.update_stock_basic()
                result.industry_records_updated = basic.get("records_updated", 0)
            if not skip_dragon:
                dragon_date = None
                if end_date:
                    dragon_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}" if len(end_date) == 8 else end_date
                dragon = self.update_dragon_eye(dragon_date)
                result.limit_status_records = dragon.get("records_updated", 0)
            if not skip_factors:
                factors = self.update_factors(start_date, end_date)
                result.factor_records_computed = factors.get("factors_computed", 0)
            result.success = True
            result.message = f"update completed in {time.time() - started:.1f}s"
        except Exception as exc:
            result.success = False
            result.message = str(exc)
            result.errors.append(str(exc))
            logger.exception("full update failed")
        return result


def run_unified_update(**kwargs) -> UpdateResult:
    return UnifiedDataUpdater().run_full_update(**kwargs)


if __name__ == "__main__":
    update_result = run_unified_update()
    print(update_result)
