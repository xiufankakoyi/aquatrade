"""Efinance provider used as the primary free realtime and board-membership source."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd

from server.data_providers.base import (
    DAILY_BARS_COLUMNS,
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
    stock_code,
    to_numeric_series,
    to_yyyymmdd,
)

logger = logging.getLogger(__name__)

_EFINANCE_AVAILABLE = False
try:
    import efinance as ef

    _EFINANCE_AVAILABLE = True
except Exception:
    ef = None


class EfinanceProvider(BaseMarketDataProvider):
    """Optional efinance adapter."""

    name = "efinance"

    def __init__(self) -> None:
        self._ef = ef if _EFINANCE_AVAILABLE else None

    def is_available(self) -> bool:
        return _EFINANCE_AVAILABLE and self._ef is not None

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.is_available(), "installed": _EFINANCE_AVAILABLE}

    def get_realtime_quotes(self, trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available():
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)
        df = self._ef.stock.get_realtime_quotes()
        if df is None or df.empty:
            return empty_frame(MARKET_SNAPSHOT_COLUMNS)

        result = pd.DataFrame(index=df.index)
        result["trade_date"] = normalize_trade_date(trade_date)
        result["symbol"] = normalize_symbols(pick_column(df, ["股票代码", "代码", "code"]))
        result["stock_name"] = pick_column(df, ["股票名称", "名称", "name"]).astype(str)
        result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "change_rate"]))
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
                df = self._ef.stock.get_quote_history(
                    stock_codes=stock_code(symbol),
                    beg=to_yyyymmdd(start_date),
                    end=to_yyyymmdd(end_date),
                    klt=101,
                    fqt=1,
                )
                if df is None or df.empty:
                    continue
                if isinstance(df.index, pd.MultiIndex):
                    df = df.reset_index(drop=True)
                result = pd.DataFrame(index=df.index)
                result["trade_date"] = pd.to_datetime(pick_column(df, ["日期", "trade_date"])).dt.strftime("%Y-%m-%d")
                result["symbol"] = normalize_symbols(pick_column(df, ["股票代码", "代码"], symbol))
                result["stock_name"] = pick_column(df, ["股票名称", "名称"], "").astype(str)
                result["open"] = to_numeric_series(pick_column(df, ["开盘", "open"]))
                result["high"] = to_numeric_series(pick_column(df, ["最高", "high"]))
                result["low"] = to_numeric_series(pick_column(df, ["最低", "low"]))
                result["close"] = to_numeric_series(pick_column(df, ["收盘", "close"]))
                result["pre_close"] = None
                result["pct_chg"] = to_numeric_series(pick_column(df, ["涨跌幅", "涨幅", "pct_chg"]))
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
                logger.warning("Efinance daily bars failed for %s: %s", symbol, exc)
                continue
        return pd.concat(rows, ignore_index=True) if rows else empty_frame(DAILY_BARS_COLUMNS)

    def get_stock_fund_flow(self, trade_date: str, symbols: list[str] | None = None) -> pd.DataFrame:
        if not self.is_available() or not symbols:
            return empty_frame(STOCK_FUND_FLOW_COLUMNS)

        target_date = normalize_trade_date(trade_date)
        symbol_list = list(dict.fromkeys(normalize_symbols(symbols).dropna().astype(str).tolist()))
        if not symbol_list:
            return empty_frame(STOCK_FUND_FLOW_COLUMNS)

        def _fetch(symbol: str) -> pd.DataFrame:
            try:
                df = self._ef.stock.get_today_bill(stock_code(symbol))
            except Exception as exc:
                logger.debug("Efinance today bill failed for %s: %s", symbol, exc)
                return empty_frame(STOCK_FUND_FLOW_COLUMNS)
            if df is None or df.empty:
                return empty_frame(STOCK_FUND_FLOW_COLUMNS)

            time_series = pick_column(df, ["时间", "time"], "")
            if not time_series.empty:
                date_mask = time_series.astype(str).str.startswith(target_date)
                if date_mask.any():
                    df = df[date_mask]
            if df.empty:
                return empty_frame(STOCK_FUND_FLOW_COLUMNS)

            latest = df.tail(1).copy()
            result = pd.DataFrame(index=latest.index)
            result["trade_date"] = target_date
            result["symbol"] = normalize_symbols(pick_column(latest, ["股票代码", "代码", "code"], symbol))
            result["stock_name"] = pick_column(latest, ["股票名称", "名称", "name"], "").astype(str)
            result["main_net_inflow"] = to_numeric_series(pick_column(latest, ["主力净流入", "main_net_inflow"], 0))
            result["super_large_net_inflow"] = to_numeric_series(pick_column(latest, ["超大单净流入", "super_large_net_inflow"], 0))
            result["large_net_inflow"] = to_numeric_series(pick_column(latest, ["大单净流入", "large_net_inflow"], 0))
            result["small_net_inflow"] = to_numeric_series(pick_column(latest, ["小单净流入", "small_net_inflow"], 0))
            result["pct_chg"] = None
            result["provider"] = self.name + ":today_bill"
            result["updated_at"] = now_text()
            return ensure_columns(result[result["symbol"].astype(bool)], STOCK_FUND_FLOW_COLUMNS)

        rows: list[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_fetch, symbol) for symbol in symbol_list]
            for future in as_completed(futures):
                frame = future.result()
                if frame is not None and not frame.empty:
                    rows.append(frame)
        return pd.concat(rows, ignore_index=True).drop_duplicates(subset=["symbol"], keep="last") if rows else empty_frame(STOCK_FUND_FLOW_COLUMNS)

    def get_stock_basic_info(self, symbols: list[str] | None = None) -> pd.DataFrame:
        quotes = self.get_realtime_quotes()
        if quotes.empty:
            return empty_frame(STOCK_BASIC_INFO_COLUMNS)
        result = pd.DataFrame(index=quotes.index)
        result["symbol"] = quotes["symbol"]
        result["stock_name"] = quotes["stock_name"]
        result["industry"] = ""
        result["area"] = ""
        result["list_date"] = ""
        result["business_scope"] = ""
        result["main_business"] = ""
        result["provider"] = self.name
        result["updated_at"] = now_text()
        result = ensure_columns(result, STOCK_BASIC_INFO_COLUMNS)
        if symbols:
            symbol_set = set(normalize_symbols(symbols))
            result = result[result["symbol"].isin(symbol_set)]
        return result

    def get_stock_belong_boards(self, symbols: list[str], trade_date: str | None = None) -> pd.DataFrame:
        if not self.is_available() or not symbols:
            return empty_frame(STOCK_BELONG_BOARDS_COLUMNS)

        rows: list[pd.DataFrame] = []

        def _fetch(symbol: str) -> pd.DataFrame:
            try:
                df = self._ef.stock.get_belong_board(stock_code(symbol))
            except Exception as exc:
                logger.debug("Efinance belong boards failed for %s: %s", symbol, exc)
                return empty_frame(STOCK_BELONG_BOARDS_COLUMNS)
            if df is None or df.empty:
                return empty_frame(STOCK_BELONG_BOARDS_COLUMNS)

            result = pd.DataFrame(index=df.index)
            result["trade_date"] = normalize_trade_date(trade_date)
            result["symbol"] = normalize_symbols(pick_column(df, ["股票代码", "代码"], symbol))
            result["stock_name"] = pick_column(df, ["股票名称", "名称"], "").astype(str)
            result["board_code"] = pick_column(df, ["板块代码", "代码"], "").astype(str)
            result["board_name"] = pick_column(df, ["板块名称", "名称"], "").astype(str)
            result["pct_chg"] = to_numeric_series(pick_column(df, ["板块涨幅", "涨跌幅", "涨幅"]))
            result["provider"] = self.name
            result["updated_at"] = now_text()
            return ensure_columns(result[result["board_name"].astype(bool)], STOCK_BELONG_BOARDS_COLUMNS)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(_fetch, symbol) for symbol in symbols]
            for future in as_completed(futures):
                frame = future.result()
                if frame is not None and not frame.empty:
                    rows.append(frame)
        return pd.concat(rows, ignore_index=True).drop_duplicates() if rows else empty_frame(STOCK_BELONG_BOARDS_COLUMNS)
