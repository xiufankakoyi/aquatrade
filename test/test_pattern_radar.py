from datetime import datetime, timedelta

import pandas as pd

from server.pattern_lab.pattern_scanner import PatternScanner
from server.pattern_lab.pattern_templates import get_pattern_templates


def _date(offset: int) -> str:
    return (datetime(2024, 1, 2) + timedelta(days=offset)).strftime("%Y-%m-%d")


def _base_row(symbol: str, offset: int, close: float) -> dict:
    return {
        "stock_code": symbol,
        "stock_name": f"样本{symbol}",
        "trade_date": _date(offset),
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "change_pct": 0.5,
        "amount": 10000,
        "amount_rank_20d": 0.6,
        "distance_to_ma5": 1.0,
        "distance_to_20d_high": -1.0,
        "is_big_up": False,
        "is_big_down": False,
        "is_limit_up": False,
        "is_limit_down": False,
        "is_failed_limit_up": False,
        "close_near_high": False,
        "close_near_low": False,
        "high_open_low_close": False,
        "long_upper_shadow": False,
        "long_lower_shadow": False,
        "above_ma5": True,
        "below_ma5": False,
        "above_ma10": True,
        "new_high_20d": False,
        "volume_burst": False,
        "volume_shrink": False,
        "strong_attack_day": False,
        "first_divergence_day": False,
        "weak_acceptance_day": False,
        "counterattack_day": False,
        "break_board_day": False,
    }


def _strong_break_rows(symbol: str, future_success: bool = True) -> list[dict]:
    closes = [10.0, 11.0, 12.2, 11.7, 11.5, 12.5, 13.2, 13.7, 13.1, 12.9, 13.0]
    rows = [_base_row(symbol, i, close) for i, close in enumerate(closes)]
    for i in [1, 2]:
        rows[i]["strong_attack_day"] = True
        rows[i]["is_big_up"] = True
        rows[i]["close_near_high"] = True
        rows[i]["change_pct"] = 8.0
    rows[3]["first_divergence_day"] = True
    rows[3]["break_board_day"] = True
    rows[3]["long_upper_shadow"] = True
    rows[3]["change_pct"] = -4.0
    rows[5]["counterattack_day"] = True
    rows[5]["close_near_high"] = True
    rows[5]["change_pct"] = 6.5
    rows[5]["volume_burst"] = True
    if not future_success:
        for i, close in enumerate([12.0, 11.9, 11.6, 11.8, 11.7], start=6):
            rows[i]["close"] = close
            rows[i]["high"] = close * 1.01
            rows[i]["low"] = close * 0.98
    return rows


def test_pattern_templates_are_available():
    templates = get_pattern_templates()
    ids = {item["pattern_id"] for item in templates}
    assert {"strong_break_reversal", "trend_ma5_pullback", "volume_reversal_repair"}.issubset(ids)


def test_strong_break_reversal_returns_reasons_and_forward_stats():
    df = pd.DataFrame(_strong_break_rows("000001"))

    report = PatternScanner().search_dataframe(
        "strong_break_reversal",
        df,
        start_date=_date(0),
        end_date=_date(7),
        limit=10,
    )

    assert report["summary"]["total_matches"] == 1
    match = report["results"][0]
    assert match["symbol"] == "000001"
    assert match["pattern_name"] == "强势断板反包"
    assert match["hit_reasons"]
    assert match["future_return_1d"] is not None
    assert match["future_return_3d"] is not None
    assert match["success_label"] is True


def test_strong_break_reversal_rejects_small_noise():
    rows = [_base_row("000002", i, 10 + i * 0.05) for i in range(12)]
    rows[5]["counterattack_day"] = True
    rows[5]["change_pct"] = 3.2
    rows[5]["close_near_high"] = True

    report = PatternScanner().search_dataframe(
        "strong_break_reversal",
        pd.DataFrame(rows),
        start_date=_date(0),
        end_date=_date(8),
        limit=10,
    )

    assert report["summary"]["total_matches"] == 0


def test_strong_break_reversal_honors_parameter_filters():
    rows = _strong_break_rows("000005")
    rows[5]["amount"] = 3000
    rows[5]["total_mv"] = 50

    report = PatternScanner().search_dataframe(
        "strong_break_reversal",
        pd.DataFrame(rows),
        start_date=_date(0),
        end_date=_date(7),
        params={"min_amount": 5000, "min_market_cap": 100},
        limit=10,
    )

    assert report["summary"]["total_matches"] == 0


def test_pattern_report_separates_success_and_failure_samples():
    df = pd.DataFrame(_strong_break_rows("000003", future_success=True) + _strong_break_rows("000004", future_success=False))

    report = PatternScanner().search_dataframe(
        "strong_break_reversal",
        df,
        start_date=_date(0),
        end_date=_date(7),
        limit=10,
    )

    assert report["summary"]["total_matches"] == 2
    assert report["summary"]["success_cases"] == 1
    assert report["summary"]["failure_cases"] == 1
    assert report["success_samples"][0]["success_label"] is True
    assert report["failure_samples"][0]["failure_reason"]
