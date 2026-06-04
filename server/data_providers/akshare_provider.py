"""AKShare provider for A-share board, limit-up and fund-flow data."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from server.data_providers.base import (
    BOARD_FUND_FLOW_COLUMNS,
    CONCEPT_BOARD_MEMBERS_COLUMNS,
    CONCEPT_BOARDS_COLUMNS,
    DAILY_BARS_COLUMNS,
    LIMIT_UP_POOL_COLUMNS,
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
    stock_code,
    to_numeric_series,
    to_yyyymmdd,
)

logger = logging.getLogger(__name__)

_AKSHARE_AVAILABLE = False
try:
    import akshare as ak

    _AKSHARE_AVAILABLE = True
except Exception:
    ak = None


class AkshareProvider(BaseMarketDataProvider):
    """Optional AKShare adapter. Empty frames are returned when unavailable."""

    name = "akshare"

    def __init__(self) -> None:
        self._ak = ak if _AKSHARE_AVAILABLE else None

    def is_available(self) -> bool:
        return _AKSHARE_AVAILABLE and self._ak is not None

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available(), "installed": _AKSHARE_AVAILABLE}

    def get_realtime_quotes(self, trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)
        df = self._ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["symbol"] = normalize_symbols(pick_column(df, ["代码", "股票代码", "code"]))
        result["stock_name"] = pick_column(df, ["名称", "股票名称", "name"]).astype(str)
        result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "changepercent"]))
        result["close"] = to_numeric_series(pick_column(df, ["最新价", "收盘", "close"]))
        result["high"] = to_numeric_series(pick_column(df, ["最高", "high"]))
        result["low"] = to_numeric_series(pick_column(df, ["最低", "low"]))
        result["open"] = to_numeric_series(pick_column(df, ["今开", "开盘", "open"]))
        result["amount"] = to_numeric_series(pick_column(df, ["成交额", "amount"]))
        result["volume"] = to_numeric_series(pick_column(df, ["成交量", "volume"]))
        result["turnover_rate"] = to_numeric_series(pick_column(df, ["换手率", "turnover_rate"]))
        result["volume_ratio"] = to_numeric_series(pick_column(df, ["量比", "volume_ratio"]))
        result["total_market_cap"] = to_numeric_series(pick_column(df, ["总市值", "total_market_cap"]))
        result["float_market_cap"] = to_numeric_series(pick_column(df, ["流通市值", "float_market_cap"]))
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], MARKET_SNAPSHOT_COLUMNS)

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        if not self.is_available() or not symbols:
            return empty_frame(DAILY_BARS_COLUMNS)

        rows: list[pd.DataFrame] = []
        for symbol in symbols:
            try:
                df = self._ak.stock_zh_a_hist(
                    symbol=stock_code(symbol),
                    period="daily",
                    start_date=to_yyyymmdd(start_date),
                    end_date=to_yyyymmdd(end_date),
                    adjust="",
                )
                if df is None or df.empty:
                    continue
                result = pd.DataFrame(index=df.index)
                result["trade_date"] = pd.to_datetime(pick_column(df, ["日期", "trade_date"])).dt.strftime("%Y-%m-%d")
                result["symbol"] = normalize_symbols([symbol] * len(df))
                result["stock_name"] = ""
                result["open"] = to_numeric_series(pick_column(df, ["开盘", "open"]))
                result["high"] = to_numeric_series(pick_column(df, ["最高", "high"]))
                result["low"] = to_numeric_series(pick_column(df, ["最低", "low"]))
                result["close"] = to_numeric_series(pick_column(df, ["收盘", "close"]))
                result["pre_close"] = None
                result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "pct_chg"]))
                result["amount"] = to_numeric_series(pick_column(df, ["成交额", "amount"]))
                result["volume"] = to_numeric_series(pick_column(df, ["成交量", "volume"]))
                result["turnover_rate"] = to_numeric_series(pick_column(df, ["换手率", "turnover_rate"]))
                result["volume_ratio"] = None
                result["total_market_cap"] = None
                result["float_market_cap"] = None
                result["provider"] = self.name
                result["updated_at"] = now_text()
                rows.append(ensure_columns(result, DAILY_BARS_COLUMNS))
            except Exception as exc:
                logger.warning("AKShare daily bars failed for %s: %s", symbol, exc)
                continue
        return pd.concat(rows, ignore_index=True) if rows else empty_frame(DAILY_BARS_COLUMNS)

    def get_concept_boards(self, trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(CONCEPT_BOARDS_COLUMNS)

        try:
            df = self._ak.stock_board_concept_name_em()
            if df is not None and not df.empty:
                return self._normalize_concept_boards(df, trade_date, provider_suffix="em")
        except Exception as exc:
            logger.warning("AKShare EM concept boards failed: %s", exc)

        try:
            df = self._ak.stock_board_concept_name_ths()
            if df is not None and not df.empty:
                return self._normalize_concept_boards(df, trade_date, provider_suffix="ths")
        except Exception as exc:
            logger.warning("AKShare THS concept boards failed: %s", exc)

        return empty_frame(CONCEPT_BOARDS_COLUMNS)

    def _normalize_concept_boards(self, df: pd.DataFrame, trade_date: str | None, provider_suffix: str) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["board_code"] = pick_column(df, ["板块代码", "代码", "code"], "").astype(str)
        result["board_name"] = pick_column(df, ["板块名称", "名称", "name"], "").astype(str)
        result["board_type"] = f"concept_{provider_suffix}"
        result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "板块涨幅", "pct_chg"]))
        result["amount"] = to_numeric_series(pick_column(df, ["成交额", "amount"]))
        result["stock_count"] = to_numeric_series(pick_column(df, ["股票家数", "成分股数量", "公司家数", "stock_count"], 0)).fillna(0).astype(int)
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["board_name"].astype(bool)], CONCEPT_BOARDS_COLUMNS)

    def get_concept_board_members(
        self,
        board_code_or_name: str,
        trade_date: str | None = None,
        board_name: str | None = None,
    ) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)
        symbol = board_name or board_code_or_name
        try:
            df = self._ak.stock_board_concept_cons_em(symbol=symbol)
        except Exception as exc:
            logger.warning("AKShare concept members failed for %s: %s", symbol, exc)
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)
        if df is None or df.empty:
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["board_code"] = str(board_code_or_name or "")
        result["board_name"] = str(board_name or board_code_or_name or "")
        result["symbol"] = normalize_symbols(pick_column(df, ["代码", "股票代码", "code"]))
        result["stock_name"] = pick_column(df, ["名称", "股票名称", "name"]).astype(str)
        result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "pct_chg"]))
        result["amount"] = to_numeric_series(pick_column(df, ["成交额", "amount"]))
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], CONCEPT_BOARD_MEMBERS_COLUMNS)

    def get_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(LIMIT_UP_POOL_COLUMNS)
        df = self._ak.stock_zt_pool_em(date=to_yyyymmdd(trade_date))
        if df is None or df.empty:
            return empty_frame(LIMIT_UP_POOL_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["symbol"] = normalize_symbols(pick_column(df, ["代码", "股票代码", "code"]))
        result["stock_name"] = pick_column(df, ["名称", "股票名称", "name"]).astype(str)
        result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "pct_chg"]))
        result["close"] = to_numeric_series(pick_column(df, ["最新价", "收盘价", "close"]))
        result["amount"] = to_numeric_series(pick_column(df, ["成交额", "amount"]))
        result["first_limit_time"] = pick_column(df, ["首次封板时间", "first_limit_time"]).astype(str)
        result["last_limit_time"] = pick_column(df, ["最后封板时间", "last_limit_time"]).astype(str)
        result["open_count"] = to_numeric_series(pick_column(df, ["炸板次数", "打开次数", "open_count"], 0)).fillna(0).astype(int)
        result["limit_up_reason"] = pick_column(df, ["涨停原因类别", "涨停原因", "所属行业", "reason"]).astype(str)
        result["consecutive_limit_count"] = to_numeric_series(pick_column(df, ["连板数", "连续涨停", "consecutive_limit_count"], 1)).fillna(1).astype(int)
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["symbol"].astype(bool)], LIMIT_UP_POOL_COLUMNS)

    def get_board_fund_flow(self, trade_date: str) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(BOARD_FUND_FLOW_COLUMNS)
        func = getattr(self._ak, "stock_fund_flow_concept", None)
        if func is None:
            return empty_frame(BOARD_FUND_FLOW_COLUMNS)
        try:
            df = func(symbol="即时")
        except Exception as exc:
            logger.warning("AKShare concept fund flow failed: %s", exc)
            return empty_frame(BOARD_FUND_FLOW_COLUMNS)
        if df is None or df.empty:
            return empty_frame(BOARD_FUND_FLOW_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["board_name"] = pick_column(df, ["行业", "名称", "板块名称", "name"]).astype(str)
        # AKShare returns concept flow in 亿元 for this endpoint.
        result["main_net_inflow"] = to_numeric_series(pick_column(df, ["净额", "主力净流入", "main_net_inflow"])) * 100000000
        result["super_large_net_inflow"] = None
        result["large_net_inflow"] = None
        result["pct_chg"] = to_numeric_series(pick_column(df, ["行业-涨跌幅", "涨跌幅", "涨幅", "pct_chg"]))
        result["provider"] = self.name
        result["updated_at"] = now_text()
        return ensure_columns(result[result["board_name"].astype(bool)], BOARD_FUND_FLOW_COLUMNS)

    def get_stock_fund_flow(self, trade_date: str, symbols: list[str] | None = None) -> pd.DataFrame:
        return empty_frame(STOCK_FUND_FLOW_COLUMNS)

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        func = getattr(self._ak, "stock_info_a_code_name", None)
        if func is None:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        df = func()
        if df is None or df.empty:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["symbol"] = normalize_symbols(pick_column(df, ["code", "代码", "股票代码"]))
        result["stock_name"] = pick_column(df, ["name", "名称", "股票名称"]).astype(str)
        result["industry"] = ""
        result["area"] = ""
        result["list_date"] = ""
        result["business_scope"] = ""
        result["main_business"] = ""
        result["provider"] = self.name
        result["updated_at"] = now_text()
        result = ensure_columns(result[result["symbol"].astype(bool)], STOCK_BASIC_INFO_COLUMNS)
        if symbols:
            symbol_set = set(normalize_symbols(symbols))
            result = result[result["symbol"].isin(symbol_set)]
        return result
