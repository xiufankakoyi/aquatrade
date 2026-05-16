"""
Unified market data provider contracts for IndustryChainRadar.

Providers are optional adapters around third-party data libraries. They should
never raise import-time errors when an optional package is missing; unsupported
methods return an empty DataFrame and ProviderRegistry handles failover.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import pandas as pd

from server.data_sync.normalizer import normalize_symbol


MARKET_SNAPSHOT_COLUMNS = [
    "trade_date",
    "symbol",
    "stock_name",
    "pct_chg",
    "close",
    "high",
    "low",
    "open",
    "amount",
    "volume",
    "turnover_rate",
    "volume_ratio",
    "total_market_cap",
    "float_market_cap",
    "provider",
    "updated_at",
]

DAILY_BARS_COLUMNS = [
    "trade_date",
    "symbol",
    "stock_name",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "pct_chg",
    "amount",
    "volume",
    "turnover_rate",
    "volume_ratio",
    "total_market_cap",
    "float_market_cap",
    "provider",
    "updated_at",
]

CONCEPT_BOARDS_COLUMNS = [
    "trade_date",
    "board_code",
    "board_name",
    "board_type",
    "pct_chg",
    "amount",
    "stock_count",
    "provider",
    "updated_at",
]

CONCEPT_BOARD_MEMBERS_COLUMNS = [
    "trade_date",
    "board_code",
    "board_name",
    "symbol",
    "stock_name",
    "pct_chg",
    "amount",
    "provider",
    "updated_at",
]

LIMIT_UP_POOL_COLUMNS = [
    "trade_date",
    "symbol",
    "stock_name",
    "pct_chg",
    "close",
    "amount",
    "first_limit_time",
    "last_limit_time",
    "open_count",
    "limit_up_reason",
    "consecutive_limit_count",
    "provider",
    "updated_at",
]

BOARD_FUND_FLOW_COLUMNS = [
    "trade_date",
    "board_name",
    "main_net_inflow",
    "super_large_net_inflow",
    "large_net_inflow",
    "pct_chg",
    "provider",
    "updated_at",
]

STOCK_FUND_FLOW_COLUMNS = [
    "trade_date",
    "symbol",
    "stock_name",
    "main_net_inflow",
    "super_large_net_inflow",
    "large_net_inflow",
    "small_net_inflow",
    "pct_chg",
    "provider",
    "updated_at",
]

STOCK_BASIC_INFO_COLUMNS = [
    "symbol",
    "stock_name",
    "industry",
    "area",
    "list_date",
    "business_scope",
    "main_business",
    "provider",
    "updated_at",
]


class BaseMarketDataProvider:
    """Base class with optional methods for market data providers."""

    name: str = "base"

    def is_available(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available()}

    def get_realtime_quotes(self, trade_date: str | None = None) -> pd.DataFrame:
        return empty_frame(MARKET_SNAPSHOT_COLUMNS)

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        return empty_frame(DAILY_BARS_COLUMNS)

    def get_concept_boards(self, trade_date: str | None = None) -> pd.DataFrame:
        return empty_frame(CONCEPT_BOARDS_COLUMNS)

    def get_concept_board_members(
        self,
        board_code_or_name: str,
        trade_date: str | None = None,
        board_name: str | None = None,
    ) -> pd.DataFrame:
        return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)

    def get_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        return empty_frame(LIMIT_UP_POOL_COLUMNS)

    def get_board_fund_flow(self, trade_date: str) -> pd.DataFrame:
        return empty_frame(BOARD_FUND_FLOW_COLUMNS)

    def get_stock_fund_flow(self, trade_date: str) -> pd.DataFrame:
        return empty_frame(STOCK_FUND_FLOW_COLUMNS)

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        return empty_frame(STOCK_BASIC_INFO_COLUMNS)

    # Backward-compatible aliases used by the previous sync module.
    def get_market_snapshot(self, trade_date: str | None = None) -> pd.DataFrame:
        return self.get_realtime_quotes(trade_date=trade_date)

    def get_concept_members(self, concept_name: str | None = None) -> pd.DataFrame:
        return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)

    def get_stock_profile(self, symbols: list[str]) -> pd.DataFrame:
        return self.get_stock_basic_info(symbols=symbols)

    def get_news_titles(self, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        return pd.DataFrame(columns=["title", "source", "pub_date", "symbol"])


def empty_frame(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def now_text() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_trade_date(value: str | None) -> str:
    if not value or value == "today":
        return pd.Timestamp.now().strftime("%Y-%m-%d")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return pd.to_datetime(text).strftime("%Y-%m-%d")


def to_yyyymmdd(value: str | None) -> str:
    return normalize_trade_date(value).replace("-", "")


def normalize_symbols(values: Any) -> pd.Series:
    series = values if isinstance(values, pd.Series) else pd.Series(values)
    return series.astype(str).apply(lambda value: normalize_symbol(value)["symbol"])


def stock_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)["symbol"]
    return normalized.split(".")[0] if normalized else str(symbol).split(".")[0]


def pick_column(df: pd.DataFrame, candidates: Iterable[str], default: Any = None) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series([default] * len(df), index=df.index)


def to_numeric_series(series: Any) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            result[col] = None
    return result[columns]


def with_common_columns(df: pd.DataFrame, provider: str, trade_date: str | None = None) -> pd.DataFrame:
    result = df.copy()
    if trade_date is not None:
        result["trade_date"] = normalize_trade_date(trade_date)
    if "provider" not in result.columns:
        result["provider"] = provider
    if "updated_at" not in result.columns:
        result["updated_at"] = now_text()
    return result
