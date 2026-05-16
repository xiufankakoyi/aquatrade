"""Convert daily OHLCV rows into short-term research event tags."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from server.event_engine.event_schema import (
    DEFAULT_THRESHOLDS,
    EVENT_BOOL_COLUMNS,
    EVENT_OUTPUT_COLUMNS,
    EventThresholds,
)


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _to_numeric(df: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _to_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    if series.dtype == object:
        lowered = series.astype(str).str.lower()
        truthy = lowered.isin(["1", "true", "yes", "y"])
        numeric = pd.to_numeric(series, errors="coerce").fillna(0) != 0
        return truthy | numeric
    return pd.to_numeric(series, errors="coerce").fillna(0) != 0


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def _rolling_last_rank(values: np.ndarray) -> float:
    current = values[-1]
    valid = values[~np.isnan(values)]
    if len(valid) == 0 or np.isnan(current):
        return np.nan
    return float(np.sum(valid <= current) / len(valid))


def _normalize_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    normalized = parsed.dt.strftime("%Y-%m-%d")
    fallback = series.astype(str).str[:10]
    return normalized.where(parsed.notna(), fallback)


def _normalize_daily_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    symbol_col = _first_existing(out.columns, ["stock_code", "symbol", "ts_code"])
    if symbol_col is None:
        raise ValueError("daily data requires one of stock_code, symbol, or ts_code")
    if symbol_col != "stock_code":
        out["stock_code"] = out[symbol_col]

    date_col = _first_existing(out.columns, ["trade_date", "date"])
    if date_col is None:
        raise ValueError("daily data requires one of trade_date or date")
    if date_col != "trade_date":
        out["trade_date"] = out[date_col]

    out["stock_code"] = out["stock_code"].astype(str).str.strip()
    out["trade_date"] = _normalize_dates(out["trade_date"])
    return out.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)


def tag_daily_events(
    daily_df: pd.DataFrame,
    thresholds: EventThresholds = DEFAULT_THRESHOLDS,
) -> pd.DataFrame:
    """Return a DataFrame with one event-tag row per stock/date.

    The function is intentionally data-frame based so it can be tested with
    small fixtures and reused by batch stores without Flask dependencies.
    """
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(columns=EVENT_OUTPUT_COLUMNS)

    out = _normalize_daily_columns(daily_df)
    grouped = out.groupby("stock_code", group_keys=False)

    for col in ["open", "high", "low", "close", "volume", "amount", "total_mv", "turnover_rate"]:
        out[col] = _to_numeric(out, col)

    if "prev_close" in out.columns:
        out["prev_close"] = _to_numeric(out, "prev_close")
    else:
        out["prev_close"] = grouped["close"].shift(1)
    out["prev_close"] = out["prev_close"].fillna(grouped["close"].shift(1))

    change_col = _first_existing(out.columns, ["change_pct", "pct_chg"])
    if change_col is not None:
        out["change_pct"] = pd.to_numeric(out[change_col], errors="coerce")
    else:
        out["change_pct"] = (_safe_div(out["close"], out["prev_close"]) - 1.0) * 100.0

    for col in ["limit_up", "limit_down"]:
        out[col] = _to_numeric(out, col)

    for ma_col, window in [("ma5", 5), ("ma10", 10)]:
        calculated = grouped["close"].transform(lambda s: s.rolling(window, min_periods=1).mean())
        if ma_col in out.columns:
            out[ma_col] = _to_numeric(out, ma_col).fillna(calculated)
        else:
            out[ma_col] = calculated

    calculated_volume_ma5 = grouped["volume"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    if "volume_ma5" in out.columns:
        out["volume_ma5"] = _to_numeric(out, "volume_ma5").fillna(calculated_volume_ma5)
    else:
        out["volume_ma5"] = calculated_volume_ma5

    out["amount_ma20"] = grouped["amount"].transform(
        lambda s: s.rolling(thresholds.rolling_window, min_periods=1).mean()
    )
    out["amount_rank_20d"] = grouped["amount"].transform(
        lambda s: s.rolling(thresholds.rolling_window, min_periods=1).apply(_rolling_last_rank, raw=True)
    )
    out["high_20d"] = grouped["high"].transform(
        lambda s: s.rolling(thresholds.rolling_window, min_periods=1).max()
    )

    day_range = (out["high"] - out["low"]).replace(0, np.nan)
    body = (out["close"] - out["open"]).abs()
    upper_shadow = out["high"] - out[["open", "close"]].max(axis=1)
    lower_shadow = out[["open", "close"]].min(axis=1) - out["low"]

    out["is_big_up"] = out["change_pct"] >= thresholds.big_up_pct
    out["is_big_down"] = out["change_pct"] <= thresholds.big_down_pct

    if "is_limit_up" in out.columns:
        source_limit_up = _to_bool(out["is_limit_up"])
    else:
        source_limit_up = pd.Series(False, index=out.index)
    limit_price_up = out["limit_up"].notna() & (out["close"] >= out["limit_up"] * thresholds.limit_price_tolerance)
    fallback_limit_up = out["limit_up"].isna() & (out["change_pct"] >= thresholds.limit_up_pct_fallback)
    out["is_limit_up"] = source_limit_up | limit_price_up | fallback_limit_up

    if "is_limit_down" in out.columns:
        source_limit_down = _to_bool(out["is_limit_down"])
    else:
        source_limit_down = pd.Series(False, index=out.index)
    limit_price_down = out["limit_down"].notna() & (out["close"] <= out["limit_down"] / thresholds.limit_price_tolerance)
    fallback_limit_down = out["limit_down"].isna() & (out["change_pct"] <= thresholds.limit_down_pct_fallback)
    out["is_limit_down"] = source_limit_down | limit_price_down | fallback_limit_down

    out["is_failed_limit_up"] = (
        out["limit_up"].notna()
        & (out["high"] >= out["limit_up"] * thresholds.limit_price_tolerance)
        & (out["close"] < out["limit_up"] * thresholds.limit_price_tolerance)
    )

    open_gap_pct = (_safe_div(out["open"], out["prev_close"]) - 1.0) * 100.0
    out["is_gap_up"] = open_gap_pct >= thresholds.gap_pct
    out["is_gap_down"] = open_gap_pct <= -thresholds.gap_pct

    out["close_near_high"] = ((out["high"] - out["close"]) / day_range) <= thresholds.close_near_high_ratio
    out["close_near_low"] = ((out["close"] - out["low"]) / day_range) <= thresholds.close_near_low_ratio
    out["high_open_low_close"] = (
        ((out["high"] / out[["open", "close"]].max(axis=1) - 1.0) * 100.0 >= thresholds.intraday_reversal_pct)
        & (out["close"] <= out["open"])
    )

    out["long_upper_shadow"] = (
        ((upper_shadow / day_range) >= thresholds.upper_shadow_ratio)
        & (upper_shadow >= body.replace(0, np.nan).fillna(0.01) * thresholds.shadow_to_body_ratio)
    )
    out["long_lower_shadow"] = (
        ((lower_shadow / day_range) >= thresholds.lower_shadow_ratio)
        & (lower_shadow >= body.replace(0, np.nan).fillna(0.01) * thresholds.shadow_to_body_ratio)
    )

    out["above_ma5"] = out["close"] > out["ma5"]
    out["below_ma5"] = out["close"] < out["ma5"]
    out["above_ma10"] = out["close"] > out["ma10"]
    out["new_high_20d"] = out["high"] >= out["high_20d"]
    out["distance_to_ma5"] = (_safe_div(out["close"], out["ma5"]) - 1.0) * 100.0
    out["distance_to_20d_high"] = (_safe_div(out["close"], out["high_20d"]) - 1.0) * 100.0

    out["volume_burst"] = (
        (out["volume_ma5"].notna() & (out["volume"] >= out["volume_ma5"] * thresholds.volume_burst_multiplier))
        | (out["amount_ma20"].notna() & (out["amount"] >= out["amount_ma20"] * thresholds.volume_burst_multiplier))
    )
    out["volume_shrink"] = out["volume_ma5"].notna() & (
        out["volume"] <= out["volume_ma5"] * thresholds.volume_shrink_multiplier
    )

    out["strong_attack_day"] = out["is_limit_up"] | (out["is_big_up"] & out["close_near_high"])

    event_grouped = out.groupby("stock_code", group_keys=False)

    prior_strong_count = event_grouped["strong_attack_day"].transform(
        lambda s: s.shift(1).rolling(thresholds.strong_prior_days, min_periods=1).sum()
    )
    prev_limit_up = event_grouped["is_limit_up"].shift(1).fillna(False).astype(bool)
    prev_strong = event_grouped["strong_attack_day"].shift(1).fillna(False).astype(bool)
    prev_high = event_grouped["high"].shift(1)
    prev_pct = event_grouped["change_pct"].shift(1)

    out["break_board_day"] = (
        (prev_limit_up | prev_strong)
        & (~out["is_limit_up"])
        & (
            (out["change_pct"] < thresholds.counterattack_pct)
            | out["close_near_low"]
            | out["long_upper_shadow"]
        )
    )

    out["first_divergence_day"] = (
        (prior_strong_count >= thresholds.strong_prior_count)
        & (~out["strong_attack_day"])
        & (
            out["break_board_day"]
            | out["is_failed_limit_up"]
            | out["long_upper_shadow"]
            | out["high_open_low_close"]
            | out["is_big_down"]
        )
    )

    event_grouped = out.groupby("stock_code", group_keys=False)

    recent_divergence = event_grouped["first_divergence_day"].transform(
        lambda s: s.shift(1).rolling(2, min_periods=1).max()
    ).fillna(False).astype(bool)
    recent_weak = event_grouped["is_big_down"].transform(
        lambda s: s.shift(1).rolling(2, min_periods=1).max()
    ).fillna(False).astype(bool)

    out["counterattack_day"] = (
        ((out["change_pct"] >= thresholds.counterattack_pct) | out["is_big_up"])
        & out["close_near_high"]
        & ((out["close"] > prev_high) | (out["change_pct"] >= thresholds.big_up_pct))
        & (recent_divergence | recent_weak | (prev_pct < 0).fillna(False))
    )

    recent_divergence_or_break = event_grouped["first_divergence_day"].transform(
        lambda s: s.shift(1).rolling(2, min_periods=1).max()
    ).fillna(False).astype(bool) | event_grouped["break_board_day"].transform(
        lambda s: s.shift(1).rolling(2, min_periods=1).max()
    ).fillna(False).astype(bool)
    out["weak_acceptance_day"] = (
        recent_divergence_or_break
        & (~out["counterattack_day"])
        & ((out["change_pct"] <= 0) | out["close_near_low"] | out["below_ma5"])
    )

    for col in EVENT_BOOL_COLUMNS:
        if col not in out.columns:
            out[col] = False
        out[col] = out[col].fillna(False).astype(bool)

    if "stock_name" not in out.columns:
        out["stock_name"] = None

    out["created_at"] = datetime.now(timezone.utc).isoformat()

    for col in EVENT_OUTPUT_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    return out[EVENT_OUTPUT_COLUMNS + ["created_at"]].copy()
