from pathlib import Path

import pandas as pd

from server.event_engine.daily_event_tagger import tag_daily_events
from server.event_engine.event_store import DailyEventTagStore


def test_tag_daily_events_detects_attack_and_limit_up():
    source = pd.DataFrame(
        [
            {
                "stock_code": "000001",
                "trade_date": "2024-01-02",
                "open": 10.0,
                "high": 10.62,
                "low": 9.92,
                "close": 10.55,
                "prev_close": 10.0,
                "change_pct": 5.5,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "ma5": 10.1,
                "ma10": 9.9,
            },
            {
                "stock_code": "000001",
                "trade_date": "2024-01-03",
                "open": 10.7,
                "high": 11.61,
                "low": 10.6,
                "close": 11.6,
                "prev_close": 10.55,
                "change_pct": 9.95,
                "volume": 10000,
                "amount": 116000,
                "limit_up": 11.6,
                "limit_down": 9.5,
                "ma5": 10.5,
                "ma10": 10.0,
            },
        ]
    )

    tags = tag_daily_events(source)

    first = tags.iloc[0]
    second = tags.iloc[1]
    assert bool(first["is_big_up"]) is True
    assert bool(first["close_near_high"]) is True
    assert bool(first["strong_attack_day"]) is True
    assert bool(second["is_limit_up"]) is True
    assert bool(second["volume_burst"]) is True


def test_tag_daily_events_handles_missing_limit_fields():
    source = pd.DataFrame(
        [
            {
                "symbol": "000002",
                "date": "2024-01-02",
                "open": 20.0,
                "high": 20.6,
                "low": 19.8,
                "close": 20.2,
                "prev_close": 20.0,
                "volume": 1000,
                "amount": 20200,
            },
            {
                "symbol": "000002",
                "date": "2024-01-03",
                "open": 19.7,
                "high": 20.0,
                "low": 19.0,
                "close": 19.1,
                "prev_close": 20.2,
                "volume": 800,
                "amount": 15280,
            },
        ]
    )

    tags = tag_daily_events(source)

    assert "stock_code" in tags.columns
    assert "trade_date" in tags.columns
    assert "is_failed_limit_up" in tags.columns
    assert tags["is_failed_limit_up"].tolist() == [False, False]
    assert tags["distance_to_ma5"].notna().all()


def test_daily_event_store_generate_and_query_with_loader(tmp_path: Path):
    source = pd.DataFrame(
        [
            {
                "stock_code": "000003",
                "trade_date": "2024-01-02",
                "open": 10.0,
                "high": 10.62,
                "low": 9.92,
                "close": 10.55,
                "prev_close": 10.0,
                "change_pct": 5.5,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "ma5": 10.1,
                "ma10": 9.9,
            },
            {
                "stock_code": "000003",
                "trade_date": "2024-01-03",
                "open": 10.6,
                "high": 10.8,
                "low": 10.1,
                "close": 10.2,
                "prev_close": 10.55,
                "change_pct": -3.32,
                "volume": 600,
                "amount": 6120,
                "limit_up": 11.61,
                "limit_down": 9.5,
                "ma5": 10.2,
                "ma10": 10.0,
            },
        ]
    )

    store = DailyEventTagStore(db_path=tmp_path / "events.db")

    def loader(start_date, end_date, symbols):
        return source

    summary = store.generate_daily_event_tags(
        "2024-01-02",
        "2024-01-03",
        symbols=["000003"],
        data_loader=loader,
    )
    rows = store.query_event_tags(
        "2024-01-02",
        "2024-01-03",
        symbols=["000003"],
        filters={"strong_attack_day": True},
    )

    assert summary["rows_stored"] == 2
    assert len(rows) == 1
    assert rows[0]["stock_code"] == "000003"
    assert rows[0]["strong_attack_day"] is True
