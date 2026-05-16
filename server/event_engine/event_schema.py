"""Schema and thresholds for daily event tags."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass(frozen=True)
class EventThresholds:
    big_up_pct: float = 5.0
    big_down_pct: float = -5.0
    limit_up_pct_fallback: float = 9.5
    limit_down_pct_fallback: float = -9.5
    limit_price_tolerance: float = 0.999
    gap_pct: float = 2.0
    close_near_high_ratio: float = 0.2
    close_near_low_ratio: float = 0.2
    upper_shadow_ratio: float = 0.45
    lower_shadow_ratio: float = 0.45
    shadow_to_body_ratio: float = 2.0
    intraday_reversal_pct: float = 3.0
    volume_burst_multiplier: float = 1.8
    volume_shrink_multiplier: float = 0.65
    ma_near_pct: float = 2.0
    counterattack_pct: float = 3.0
    strong_prior_days: int = 5
    strong_prior_count: int = 2
    rolling_window: int = 20
    lookback_calendar_days: int = 45

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


DEFAULT_THRESHOLDS = EventThresholds()

IDENTITY_COLUMNS: List[str] = [
    "stock_code",
    "stock_name",
    "trade_date",
]

SOURCE_CONTEXT_COLUMNS: List[str] = [
    "open",
    "high",
    "low",
    "close",
    "prev_close",
    "change_pct",
    "volume",
    "amount",
    "total_mv",
    "turnover_rate",
    "limit_up",
    "limit_down",
]

EVENT_BOOL_COLUMNS: List[str] = [
    "is_big_up",
    "is_big_down",
    "is_limit_up",
    "is_limit_down",
    "is_failed_limit_up",
    "is_gap_up",
    "is_gap_down",
    "close_near_high",
    "close_near_low",
    "high_open_low_close",
    "long_upper_shadow",
    "long_lower_shadow",
    "above_ma5",
    "below_ma5",
    "above_ma10",
    "new_high_20d",
    "volume_burst",
    "volume_shrink",
    "strong_attack_day",
    "first_divergence_day",
    "weak_acceptance_day",
    "counterattack_day",
    "break_board_day",
]

EVENT_NUMERIC_COLUMNS: List[str] = [
    "ma5",
    "ma10",
    "volume_ma5",
    "amount_rank_20d",
    "distance_to_ma5",
    "distance_to_20d_high",
]

EVENT_OUTPUT_COLUMNS: List[str] = (
    IDENTITY_COLUMNS
    + SOURCE_CONTEXT_COLUMNS
    + EVENT_BOOL_COLUMNS
    + EVENT_NUMERIC_COLUMNS
)

SQLITE_COLUMN_TYPES: Dict[str, str] = {
    "stock_code": "TEXT NOT NULL",
    "stock_name": "TEXT",
    "trade_date": "TEXT NOT NULL",
    "open": "REAL",
    "high": "REAL",
    "low": "REAL",
    "close": "REAL",
    "prev_close": "REAL",
    "change_pct": "REAL",
    "volume": "REAL",
    "amount": "REAL",
    "total_mv": "REAL",
    "turnover_rate": "REAL",
    "limit_up": "REAL",
    "limit_down": "REAL",
    "ma5": "REAL",
    "ma10": "REAL",
    "volume_ma5": "REAL",
    "amount_rank_20d": "REAL",
    "distance_to_ma5": "REAL",
    "distance_to_20d_high": "REAL",
    **{name: "INTEGER" for name in EVENT_BOOL_COLUMNS},
}

