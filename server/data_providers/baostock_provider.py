"""Baostock fallback provider for historical daily bars."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from server.data_providers.base import (
    DAILY_BARS_COLUMNS,
    STOCK_BASIC_INFO_COLUMNS,
    BaseMarketDataProvider,
    empty_frame,
    ensure_columns,
    normalize_symbols,
    normalize_trade_date,
    now_text,
    stock_code,
    to_numeric_series,
)

logger = logging.getLogger(__name__)

_BAOSTOCK_AVAILABLE = False
try:
    import baostock as bs

    _BAOSTOCK_AVAILABLE = True
except Exception:
    bs = None


class BaostockProvider(BaseMarketDataProvider):
    """Optional Baostock adapter."""

    name = "baostock"

    def __init__(self) -> None:
        self._bs = bs if _BAOSTOCK_AVAILABLE else None

    def is_available(self) -> bool:
        return _BAOSTOCK_AVAILABLE and self._bs is not None

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available(), "installed": _BAOSTOCK_AVAILABLE}

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        if not self.is_available() or not symbols:
            return empty_frame(DAILY_BARS_COLUMNS)
        login = self._bs.login()
        if getattr(login, "error_code", "0") != "0":
            return empty_frame(DAILY_BARS_COLUMNS)
        try:
            frames: list[pd.DataFrame] = []
            fields = "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn,tradestatus"
            for symbol in symbols:
                bs_code = _to_baostock_code(symbol)
                rs = self._bs.query_history_k_data_plus(
                    bs_code,
                    fields,
                    start_date=normalize_trade_date(start_date),
                    end_date=normalize_trade_date(end_date),
                    frequency="d",
                    adjustflag="2",
                )
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if not rows:
                    continue
                df = pd.DataFrame(rows, columns=rs.fields)
                result = pd.DataFrame(index=df.index)
                result["trade_date"] = df["date"].astype(str)
                result["symbol"] = normalize_symbols(df["code"].astype(str).str.replace(".", "", regex=False))
                result["stock_name"] = ""
                result["open"] = to_numeric_series(df["open"])
                result["high"] = to_numeric_series(df["high"])
                result["low"] = to_numeric_series(df["low"])
                result["close"] = to_numeric_series(df["close"])
                result["pre_close"] = to_numeric_series(df["preclose"])
                result["pct_chg"] = to_numeric_series(df["pctChg"])
                result["amount"] = to_numeric_series(df["amount"])
                result["volume"] = to_numeric_series(df["volume"])
                result["turnover_rate"] = to_numeric_series(df["turn"])
                result["volume_ratio"] = None
                result["total_market_cap"] = None
                result["float_market_cap"] = None
                result["provider"] = self.name
                result["updated_at"] = now_text()
                frames.append(ensure_columns(result, DAILY_BARS_COLUMNS))
            return pd.concat(frames, ignore_index=True) if frames else empty_frame(DAILY_BARS_COLUMNS)
        finally:
            try:
                self._bs.logout()
            except Exception:
                pass

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        if not self.is_available() or not symbols:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        login = self._bs.login()
        if getattr(login, "error_code", "0") != "0":
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        try:
            frames = []
            for symbol in symbols:
                rs = self._bs.query_stock_basic(code=_to_baostock_code(symbol))
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    frames.append(pd.DataFrame(rows, columns=rs.fields))
            if not frames:
                return empty_frame(STOCK_BASIC_INFO_COLUMNS)
            df = pd.concat(frames, ignore_index=True)
            result = pd.DataFrame(index=df.index)
            result["symbol"] = normalize_symbols(df["code"].astype(str).str.replace(".", "", regex=False))
            result["stock_name"] = df.get("code_name", "").astype(str)
            result["industry"] = ""
            result["area"] = ""
            result["list_date"] = df.get("ipoDate", "").astype(str)
            result["business_scope"] = ""
            result["main_business"] = ""
            result["provider"] = self.name
            result["updated_at"] = now_text()
            return ensure_columns(result[result["symbol"].astype(bool)], STOCK_BASIC_INFO_COLUMNS)
        finally:
            try:
                self._bs.logout()
            except Exception:
                pass


def _to_baostock_code(symbol: str) -> str:
    normalized = normalize_symbols([symbol]).iloc[0]
    code = stock_code(normalized)
    suffix = normalized.split(".")[-1].lower() if "." in normalized else ("sh" if code.startswith("6") else "sz")
    return f"{suffix}.{code}"
