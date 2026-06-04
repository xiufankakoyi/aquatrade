"""Tushare provider for fallback daily bars, THS concepts and stock basics."""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from server.data_providers.base import (
    BOARD_FUND_FLOW_COLUMNS,
    CONCEPT_BOARD_MEMBERS_COLUMNS,
    CONCEPT_BOARDS_COLUMNS,
    DAILY_BARS_COLUMNS,
    MARKET_SNAPSHOT_COLUMNS,
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
    to_yyyymmdd,
)

logger = logging.getLogger(__name__)


class TushareProvider(BaseMarketDataProvider):
    """Optional Tushare adapter. Requires TUSHARE_TOKEN."""

    name = "tushare"

    def __init__(self) -> None:
        self._token = os.getenv("TUSHARE_TOKEN", "").strip()
        self._pro = None
        if self._token:
            try:
                import tushare as ts

                self._pro = ts.pro_api(self._token)
            except Exception as exc:
                logger.warning("Tushare init failed: %s", exc)

    def is_available(self) -> bool:
        return bool(self._token and self._pro is not None)

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available(), "token_exists": bool(self._token)}

    def get_realtime_quotes(self, trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)
        date_text = to_yyyymmdd(trade_date)
        daily = self._pro.daily(trade_date=date_text)
        if daily is None or daily.empty:
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)
        basic = self._fetch_daily_basic(date_text)
        df = daily.merge(basic, on=["ts_code", "trade_date"], how="left") if not basic.empty else daily

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(date_text)
        result["symbol"] = normalize_symbols(df["ts_code"])
        result["stock_name"] = ""
        result["pct_chg"] = to_numeric_series(pick_column(df, ["pct_chg"]))
        result["close"] = to_numeric_series(pick_column(df, ["close"]))
        result["high"] = to_numeric_series(pick_column(df, ["high"]))
        result["low"] = to_numeric_series(pick_column(df, ["low"]))
        result["open"] = to_numeric_series(pick_column(df, ["open"]))
        result["amount"] = to_numeric_series(pick_column(df, ["amount"])) * 1000
        result["volume"] = to_numeric_series(pick_column(df, ["vol"])) * 100
        result["turnover_rate"] = to_numeric_series(pick_column(df, ["turnover_rate"]))
        result["volume_ratio"] = to_numeric_series(pick_column(df, ["volume_ratio"]))
        result["total_market_cap"] = to_numeric_series(pick_column(df, ["total_mv"])) * 10000
        result["float_market_cap"] = to_numeric_series(pick_column(df, ["circ_mv"])) * 10000
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], MARKET_SNAPSHOT_COLUMNS)

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(DAILY_BARS_COLUMNS)
        kwargs: dict[str, Any] = {"start_date": to_yyyymmdd(start_date), "end_date": to_yyyymmdd(end_date)}
        if symbols and len(symbols) == 1:
            kwargs["ts_code"] = normalize_symbols(symbols).iloc[0]
        df = self._pro.daily(**kwargs)
        if df is None or df.empty:
            return empty_frame(DAILY_BARS_COLUMNS)
        if symbols and len(symbols) > 1:
            symbol_set = set(normalize_symbols(symbols))
            df = df[df["ts_code"].isin(symbol_set)]
        if df.empty:
            return empty_frame(DAILY_BARS_COLUMNS)

        basic_frames: list[pd.DataFrame] = []
        for date_text in sorted(df["trade_date"].dropna().astype(str).unique()):
            basic = self._fetch_daily_basic(date_text)
            if not basic.empty:
                basic_frames.append(basic)
        if basic_frames:
            basic_df = pd.concat(basic_frames, ignore_index=True)
            df = df.merge(basic_df, on=["ts_code", "trade_date"], how="left")

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        result["symbol"] = normalize_symbols(df["ts_code"])
        result["stock_name"] = ""
        result["open"] = to_numeric_series(pick_column(df, ["open"]))
        result["high"] = to_numeric_series(pick_column(df, ["high"]))
        result["low"] = to_numeric_series(pick_column(df, ["low"]))
        result["close"] = to_numeric_series(pick_column(df, ["close"]))
        result["pre_close"] = to_numeric_series(pick_column(df, ["pre_close"]))
        result["pct_chg"] = to_numeric_series(pick_column(df, ["pct_chg"]))
        result["amount"] = to_numeric_series(pick_column(df, ["amount"])) * 1000
        result["volume"] = to_numeric_series(pick_column(df, ["vol"])) * 100
        result["turnover_rate"] = to_numeric_series(pick_column(df, ["turnover_rate"]))
        result["volume_ratio"] = to_numeric_series(pick_column(df, ["volume_ratio"]))
        result["total_market_cap"] = to_numeric_series(pick_column(df, ["total_mv"])) * 10000
        result["float_market_cap"] = to_numeric_series(pick_column(df, ["circ_mv"])) * 10000
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], DAILY_BARS_COLUMNS)

    def get_concept_boards(self, trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(CONCEPT_BOARDS_COLUMNS)
        df = self._pro.ths_index()
        if df is None or df.empty:
            return empty_frame(CONCEPT_BOARDS_COLUMNS)
        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["board_code"] = pick_column(df, ["ts_code", "code"]).astype(str)
        result["board_name"] = pick_column(df, ["name"]).astype(str)
        result["board_type"] = pick_column(df, ["type"], "concept").astype(str).replace("", "concept")
        result["pct_chg"] = None
        result["amount"] = None
        result["stock_count"] = to_numeric_series(pick_column(df, ["count", "stock_count"], 0)).fillna(0).astype(int)
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["board_name"].astype(bool)], CONCEPT_BOARDS_COLUMNS)

    def get_concept_board_members(
        self,
        board_code_or_name: str,
        trade_date: str | None = None,
        board_name: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available() or not board_code_or_name:
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)
        df = self._pro.ths_member(ts_code=board_code_or_name)
        if df is None or df.empty:
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)
        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["board_code"] = str(board_code_or_name)
        result["board_name"] = str(board_name or "")
        result["symbol"] = normalize_symbols(pick_column(df, ["con_code", "ts_code", "code"]))
        result["stock_name"] = pick_column(df, ["con_name", "name"]).astype(str)
        result["pct_chg"] = None
        result["amount"] = None
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], CONCEPT_BOARD_MEMBERS_COLUMNS)

    def get_board_fund_flow(self, trade_date: str) -> pd.DataFrame:
        return empty_frame(BOARD_FUND_FLOW_COLUMNS)

    def get_stock_fund_flow(self, trade_date: str, symbols: list[str] | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(STOCK_FUND_FLOW_COLUMNS)
        try:
            df = self._pro.moneyflow(trade_date=to_yyyymmdd(trade_date))
        except Exception:
            return empty_frame(STOCK_FUND_FLOW_COLUMNS)
        if df is None or df.empty:
            return empty_frame(STOCK_FUND_FLOW_COLUMNS)
        if symbols:
            symbol_set = set(normalize_symbols(symbols))
            df = df[df["ts_code"].isin(symbol_set)]
            if df.empty:
                return empty_frame(STOCK_FUND_FLOW_COLUMNS)
        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["symbol"] = normalize_symbols(pick_column(df, ["ts_code"]))
        result["stock_name"] = ""
        result["main_net_inflow"] = to_numeric_series(pick_column(df, ["net_mf_amount"])) * 10000
        result["super_large_net_inflow"] = to_numeric_series(pick_column(df, ["buy_elg_amount"], 0)) * 10000
        result["large_net_inflow"] = to_numeric_series(pick_column(df, ["buy_lg_amount"], 0)) * 10000
        result["small_net_inflow"] = to_numeric_series(pick_column(df, ["buy_sm_amount"], 0)) * 10000
        result["pct_chg"] = None
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], STOCK_FUND_FLOW_COLUMNS)

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        df = self._pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,list_date")
        if df is None or df.empty:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        result = pd.DataFrame(index=df.index)
        result["symbol"] = normalize_symbols(pick_column(df, ["ts_code"]))
        result["stock_name"] = pick_column(df, ["name"]).astype(str)
        result["industry"] = pick_column(df, ["industry"]).astype(str)
        result["area"] = pick_column(df, ["area"]).astype(str)
        result["list_date"] = pick_column(df, ["list_date"]).astype(str)
        result["business_scope"] = ""
        result["main_business"] = ""
        result["provider"] = self.name
        result["updated_at"] = now_text()
        result = ensure_columns(result[result["symbol"].astype(bool)], STOCK_BASIC_INFO_COLUMNS)
        if symbols:
            symbol_set = set(normalize_symbols(symbols))
            result = result[result["symbol"].isin(symbol_set)]
        return result

    def _fetch_daily_basic(self, trade_date: str) -> pd.DataFrame:
        try:
            df = self._pro.daily_basic(
                trade_date=trade_date,
                fields="ts_code,trade_date,turnover_rate,volume_ratio,total_mv,circ_mv",
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.warning("Tushare daily_basic failed for %s: %s", trade_date, exc)
            return pd.DataFrame()
