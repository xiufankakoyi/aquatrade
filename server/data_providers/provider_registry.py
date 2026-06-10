"""Provider registry with failover, local-first reads and source logging."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from config.config import Config
from server.data_providers.akshare_provider import AkshareProvider
from server.data_providers.baostock_provider import BaostockProvider
from server.data_providers.base import (
    BOARD_FUND_FLOW_COLUMNS,
    CONCEPT_BOARD_MEMBERS_COLUMNS,
    CONCEPT_BOARDS_COLUMNS,
    DAILY_BARS_COLUMNS,
    LIMIT_UP_POOL_COLUMNS,
    MARKET_SNAPSHOT_COLUMNS,
    STOCK_BELONG_BOARDS_COLUMNS,
    STOCK_BASIC_INFO_COLUMNS,
    STOCK_FUND_FLOW_COLUMNS,
    BaseMarketDataProvider,
    empty_frame,
    ensure_columns,
    normalize_symbols,
    normalize_trade_date,
    now_text,
    pick_column,
    to_numeric_series,
)
from server.data_providers.efinance_provider import EfinanceProvider
from server.data_providers.tushare_provider import TushareProvider
from server.industry_chain.loader import project_root

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Unified failover facade for market data providers."""

    def __init__(
        self,
        providers: list[BaseMarketDataProvider] | None = None,
        parquet_dir: Path | None = None,
    ) -> None:
        provider_list = providers or [
            EfinanceProvider(),
            AkshareProvider(),
            TushareProvider(),
            BaostockProvider(),
        ]
        self.providers: dict[str, BaseMarketDataProvider] = {provider.name: provider for provider in provider_list}
        self.parquet_dir = parquet_dir or (project_root() / "data" / "parquet_data")
        self.logs: list[dict[str, Any]] = []

    def get_realtime_quotes(self, trade_date: str | None = None) -> pd.DataFrame:
        return self._failover(
            method_name="get_realtime_quotes",
            provider_order=["efinance", "akshare", "tushare"],
            columns=MARKET_SNAPSHOT_COLUMNS,
            trade_date=trade_date,
        )

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        provider_order = ["tushare", "efinance", "akshare", "baostock"]
        if Config.parquet_fallback_enabled():
            provider_order.insert(0, "local_parquet")
        return self._failover(
            method_name="get_daily_bars",
            provider_order=provider_order,
            columns=DAILY_BARS_COLUMNS,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
        )

    def get_concept_boards(self, trade_date: str | None = None) -> pd.DataFrame:
        return self._failover(
            method_name="get_concept_boards",
            provider_order=["akshare", "tushare"],
            columns=CONCEPT_BOARDS_COLUMNS,
            trade_date=trade_date,
        )

    def get_concept_board_members(
        self,
        board_code_or_name: str,
        trade_date: str | None = None,
        board_name: str | None = None,
    ) -> pd.DataFrame:
        return self._failover(
            method_name="get_concept_board_members",
            provider_order=["akshare", "tushare"],
            columns=CONCEPT_BOARD_MEMBERS_COLUMNS,
            board_code_or_name=board_code_or_name,
            trade_date=trade_date,
            board_name=board_name,
            context=board_name or board_code_or_name,
        )

    def get_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        return self._failover(
            method_name="get_limit_up_pool",
            provider_order=["akshare"],
            columns=LIMIT_UP_POOL_COLUMNS,
            trade_date=trade_date,
        )

    def get_board_fund_flow(self, trade_date: str) -> pd.DataFrame:
        return self._failover(
            method_name="get_board_fund_flow",
            provider_order=["efinance", "akshare"],
            columns=BOARD_FUND_FLOW_COLUMNS,
            trade_date=trade_date,
        )

    def get_stock_fund_flow(self, trade_date: str, symbols: list[str] | None = None) -> pd.DataFrame:
        return self._failover(
            method_name="get_stock_fund_flow",
            provider_order=["efinance", "akshare", "tushare"],
            columns=STOCK_FUND_FLOW_COLUMNS,
            trade_date=trade_date,
            symbols=symbols,
            context=f"{len(symbols)} symbols" if symbols else "",
        )

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        provider_order = ["tushare", "akshare", "efinance", "baostock"]
        if Config.parquet_fallback_enabled():
            provider_order.insert(0, "local_stock_info")
        return self._failover(
            method_name="get_stock_basic_info",
            provider_order=provider_order,
            columns=STOCK_BASIC_INFO_COLUMNS,
            symbols=symbols,
        )

    def get_stock_belong_boards(self, symbols: list[str], trade_date: str | None = None) -> pd.DataFrame:
        return self._failover(
            method_name="get_stock_belong_boards",
            provider_order=["efinance"],
            columns=STOCK_BELONG_BOARDS_COLUMNS,
            symbols=symbols,
            trade_date=trade_date,
            context=f"{len(symbols)} symbols",
        )

    def status(self) -> dict[str, Any]:
        return {name: provider.health() for name, provider in self.providers.items()}

    def log_frame(self) -> pd.DataFrame:
        columns = [
            "trade_date",
            "method",
            "context",
            "provider_used",
            "success",
            "row_count",
            "fetch_time",
            "error_message",
            "updated_at",
        ]
        if not self.logs:
            return empty_frame(columns)
        return ensure_columns(pd.DataFrame(self.logs), columns)

    def _failover(
        self,
        method_name: str,
        provider_order: list[str],
        columns: list[str],
        **kwargs: Any,
    ) -> pd.DataFrame:
        context = str(kwargs.pop("context", "") or "")
        trade_date = kwargs.get("trade_date") or kwargs.get("end_date") or kwargs.get("start_date")
        last_error = ""
        for provider_name in provider_order:
            start = time.perf_counter()
            try:
                df = self._call_provider(provider_name, method_name, **kwargs)
                elapsed = round(time.perf_counter() - start, 4)
                if df is not None and not df.empty:
                    result = ensure_columns(df, columns)
                    self._record_log(trade_date, method_name, context, provider_name, True, len(result), elapsed, "")
                    return result
                last_error = "empty result"
                self._record_log(trade_date, method_name, context, provider_name, False, 0, elapsed, last_error)
            except Exception as exc:
                elapsed = round(time.perf_counter() - start, 4)
                last_error = str(exc)
                self._record_log(trade_date, method_name, context, provider_name, False, 0, elapsed, last_error)
                logger.warning("Provider %s.%s failed: %s", provider_name, method_name, exc)
        return empty_frame(columns)

    def _call_provider(self, provider_name: str, method_name: str, **kwargs: Any) -> pd.DataFrame:
        if provider_name == "local_parquet":
            return self._get_local_daily_bars(
                start_date=str(kwargs.get("start_date") or ""),
                end_date=str(kwargs.get("end_date") or ""),
                symbols=kwargs.get("symbols"),
            )
        if provider_name == "local_stock_info":
            return self._get_local_stock_basic_info(symbols=kwargs.get("symbols"))

        provider = self.providers.get(provider_name)
        if provider is None:
            raise RuntimeError("provider not registered")
        if not provider.is_available():
            raise RuntimeError("provider unavailable")
        method: Callable[..., pd.DataFrame] | None = getattr(provider, method_name, None)
        if method is None:
            raise RuntimeError("method unsupported")
        return method(**kwargs)

    def _get_local_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        parquet_path = self.parquet_dir / "stock_daily.parquet"
        if not parquet_path.exists():
            return empty_frame(DAILY_BARS_COLUMNS)
        try:
            import polars as pl

            lf = pl.scan_parquet(str(parquet_path))
            schema_names = set(lf.collect_schema().names())
            date_col = "trade_date" if "trade_date" in schema_names else "date"
            start_norm = normalize_trade_date(start_date)
            end_norm = normalize_trade_date(end_date)
            lf = lf.filter((pl.col(date_col).cast(pl.Utf8) >= start_norm) & (pl.col(date_col).cast(pl.Utf8) <= end_norm))
            symbol_col = _first_existing(schema_names, ["symbol", "ts_code", "stock_code", "code"])
            if symbols and symbol_col:
                symbol_values = set(normalize_symbols(symbols))
                code_values = {item.split(".")[0] for item in symbol_values}
                lf = lf.filter(pl.col(symbol_col).cast(pl.Utf8).is_in(list(symbol_values | code_values)))
            df = lf.collect().to_pandas()
        except Exception:
            df = pd.read_parquet(parquet_path)

        if df.empty:
            return empty_frame(DAILY_BARS_COLUMNS)
        if "trade_date" not in df.columns and "date" in df.columns:
            df["trade_date"] = df["date"]
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        start_norm = normalize_trade_date(start_date)
        end_norm = normalize_trade_date(end_date)
        df = df[(df["trade_date"] >= start_norm) & (df["trade_date"] <= end_norm)]

        raw_symbol = pick_column(df, ["symbol", "ts_code", "stock_code", "code"])
        result = pd.DataFrame(index=df.index)
        result["trade_date"] = df["trade_date"]
        result["symbol"] = normalize_symbols(raw_symbol)
        result["stock_name"] = pick_column(df, ["stock_name", "stockName", "name"], "").astype(str)
        result["open"] = to_numeric_series(pick_column(df, ["open"]))
        result["high"] = to_numeric_series(pick_column(df, ["high"]))
        result["low"] = to_numeric_series(pick_column(df, ["low"]))
        result["close"] = to_numeric_series(pick_column(df, ["close"]))
        result["pre_close"] = to_numeric_series(pick_column(df, ["pre_close", "prev_close"]))
        result["pct_chg"] = to_numeric_series(pick_column(df, ["pct_chg", "change_pct"]))
        result["amount"] = to_numeric_series(pick_column(df, ["amount", "turnover"]))
        result["volume"] = to_numeric_series(pick_column(df, ["volume", "vol"]))
        result["turnover_rate"] = to_numeric_series(pick_column(df, ["turnover_rate"]))
        result["volume_ratio"] = to_numeric_series(pick_column(df, ["volume_ratio"]))
        result["total_market_cap"] = to_numeric_series(pick_column(df, ["total_market_cap", "total_mv"]))
        result["float_market_cap"] = to_numeric_series(pick_column(df, ["float_market_cap", "float_mv", "circ_mv"]))
        result["provider"] = "local_parquet"
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], DAILY_BARS_COLUMNS)

    def _get_local_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        parquet_path = self.parquet_dir / "stock_info.parquet"
        if not parquet_path.exists():
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        df = pd.read_parquet(parquet_path)
        if df.empty:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        result = pd.DataFrame(index=df.index)
        result["symbol"] = normalize_symbols(pick_column(df, ["symbol", "ts_code", "stock_code", "code"]))
        result["stock_name"] = pick_column(df, ["stock_name", "stockName", "name"], "").astype(str)
        result["industry"] = pick_column(df, ["industry"], "").astype(str)
        result["area"] = pick_column(df, ["area"], "").astype(str)
        result["list_date"] = pick_column(df, ["list_date"], "").astype(str)
        result["business_scope"] = pick_column(df, ["business_scope"], "").astype(str)
        result["main_business"] = pick_column(df, ["main_business"], "").astype(str)
        result["provider"] = "local_stock_info"
        result["updated_at"] = now_text()
        result = ensure_columns(result[result["symbol"].astype(bool)], STOCK_BASIC_INFO_COLUMNS)
        if symbols:
            symbol_set = set(normalize_symbols(symbols))
            result = result[result["symbol"].isin(symbol_set)]
        return result

    def _record_log(
        self,
        trade_date: str | None,
        method: str,
        context: str,
        provider: str,
        success: bool,
        row_count: int,
        fetch_time: float,
        error_message: str,
    ) -> None:
        self.logs.append(
            {
                "trade_date": normalize_trade_date(trade_date),
                "method": method,
                "context": context,
                "provider_used": provider,
                "success": success,
                "row_count": int(row_count),
                "fetch_time": float(fetch_time),
                "error_message": error_message,
                "updated_at": now_text(),
            }
        )


def _first_existing(names: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in names:
            return candidate
    return None
