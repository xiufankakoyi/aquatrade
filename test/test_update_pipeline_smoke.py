from __future__ import annotations

import json
from pathlib import Path

import lancedb
import pandas as pd
import polars as pl

from config.config import Config
from data_svc.ingestion.dragon_eye_adapter import DragonEyeAdapter, DragonEyeTransformer
from data_svc.ingestion.gap_checker import check_and_repair_gaps
from data_svc.spiders.dragon_spider.main import StealthCrawler
from data_svc.storage.factor_precompute_service import FactorPrecomputeService
from data_svc.storage.unified_updater import UnifiedDataUpdater


class FakeTusharePro:
    def trade_cal(self, **kwargs):
        return pd.DataFrame([{"cal_date": "20260609", "is_open": 1}])

    def daily(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260609",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "pre_close": 10.0,
                    "change": 0.2,
                    "pct_chg": 2.0,
                    "vol": 1000.0,
                    "amount": 10200.0,
                }
            ]
        )

    def daily_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260609",
                    "turnover_rate": 1.2,
                    "turnover_rate_f": 2.3,
                    "volume_ratio": 1.5,
                    "total_mv": 100000.0,
                    "circ_mv": 80000.0,
                    "total_share": 10000.0,
                    "float_share": 8000.0,
                    "free_share": 5000.0,
                    "dv_ratio": 1.1,
                    "dv_ttm": 1.2,
                }
            ]
        )

    def adj_factor(self, **kwargs):
        return pd.DataFrame(
            [{"ts_code": "000001.SZ", "trade_date": "20260609", "adj_factor": 3.0}]
        )

    def stk_limit(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260609",
                    "up_limit": 11.0,
                    "down_limit": 9.0,
                }
            ]
        )


def _table_names(db):
    listed = db.list_tables()
    return listed.tables if hasattr(listed, "tables") else list(listed)


def test_tushare_update_fills_supported_auxiliary_fields(monkeypatch, tmp_path):
    import tushare as ts

    monkeypatch.setattr(ts, "pro_api", lambda token: FakeTusharePro())
    updater = UnifiedDataUpdater()
    updater.lancedb_path = str(tmp_path / "lancedb")

    result = updater.update_stock_daily("20260609", "20260609")

    assert result["records_added"] == 1
    db = lancedb.connect(updater.lancedb_path)
    row = pl.from_arrow(db.open_table("daily_ohlcv").to_arrow()).row(0, named=True)
    assert row["turnover_rate"] == 1.2
    assert row["turnover_free"] == 2.3
    assert row["volume_ratio"] == 1.5
    assert row["limit_up"] == 11.0
    assert row["limit_down"] == 9.0
    assert row["free_float_shares"] == 5000.0


def test_date_replacement_preserves_derived_columns_and_removes_stale_rows(tmp_path):
    updater = UnifiedDataUpdater()
    updater.lancedb_path = str(tmp_path / "lancedb")
    db = lancedb.connect(updater.lancedb_path)
    existing = pl.DataFrame(
        {
            "stock_code": ["A", "STALE"],
            "trade_date": ["2026-06-09", "2026-06-09"],
            "close": [10.0, 20.0],
            "ma5": [9.5, 19.5],
        }
    ).with_columns(pl.col("trade_date").str.to_date())
    db.create_table("daily_ohlcv", existing.to_arrow())
    incoming = pl.DataFrame(
        {
            "stock_code": ["A", "B"],
            "trade_date": ["2026-06-09", "2026-06-09"],
            "close": [11.0, 12.0],
        }
    ).with_columns(pl.col("trade_date").str.to_date())

    updater._add_or_create("daily_ohlcv", incoming, ["20260609"])

    actual = pl.from_arrow(db.open_table("daily_ohlcv").to_arrow()).sort("stock_code")
    assert actual["stock_code"].to_list() == ["A", "B"]
    assert actual.filter(pl.col("stock_code") == "A")["ma5"].item() == 9.5
    assert actual.filter(pl.col("stock_code") == "B")["ma5"].item() is None


def test_date_replacement_aligns_existing_timestamp_key(tmp_path):
    updater = UnifiedDataUpdater()
    updater.lancedb_path = str(tmp_path / "lancedb")
    db = lancedb.connect(updater.lancedb_path)
    existing = pl.DataFrame(
        {
            "symbol": ["000300.SH"],
            "trade_date": [pd.Timestamp("2026-06-09")],
            "close": [10.0],
        }
    )
    db.create_table("index_daily", existing.to_arrow())
    incoming = pl.DataFrame(
        {
            "symbol": ["000300.SH"],
            "trade_date": ["2026-06-09"],
            "close": [11.0],
        }
    ).with_columns(pl.col("trade_date").str.to_date())

    updater._add_or_create("index_daily", incoming, ["20260609"])

    actual = pl.from_arrow(db.open_table("index_daily").to_arrow())
    assert actual["close"].item() == 11.0


def test_gap_repair_removes_non_trading_rows_from_daily_and_factors(monkeypatch, tmp_path):
    db_path = str(tmp_path / "lancedb")
    monkeypatch.setattr(Config, "LANCEDB_PATH", db_path)
    db = lancedb.connect(db_path)
    keys = pl.DataFrame(
        {
            "trade_date": ["2026-04-24", "2026-04-25"],
            "stock_code": ["A", "A"],
            "close": [10.0, 99.0],
        }
    ).with_columns(pl.col("trade_date").str.to_date())
    db.create_table("daily_ohlcv", keys.to_arrow())
    db.create_table("factors", keys.select(["trade_date", "stock_code", "close"]).to_arrow())

    monkeypatch.setattr(
        "data_svc.ingestion.gap_checker.get_expected_trading_dates",
        lambda start_date, end_date: ["2026-04-24"],
    )
    result = check_and_repair_gaps(
        trading_dates=["2026-04-24", "2026-04-25"],
        auto_repair=False,
        remove_unexpected_dates=True,
    )

    assert result["removed_unexpected_dates"] == ["2026-04-25"]
    for table_name in ("daily_ohlcv", "factors"):
        actual = pl.from_arrow(db.open_table(table_name).to_arrow())
        assert actual["trade_date"].dt.strftime("%Y-%m-%d").to_list() == ["2026-04-24"]


def test_dragon_eye_merges_leader_tags_from_ladder(tmp_path):
    date_dir = tmp_path / "2026-04-30"
    date_dir.mkdir(parents=True)
    (date_dir / "limit_up_filter.json").write_text(
        json.dumps(
            {
                "data": {
                    "stocks": [
                        {
                            "code": "603095",
                            "name": "样例股票",
                            "continue_num": 4,
                            "tags": [],
                            "total_market_cap": 1_000_000_000,
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (date_dir / "ladder_hierarchy_detail.json").write_text(
        json.dumps(
            {
                "dates": [
                    {
                        "boards": [
                            {
                                "level": 4,
                                "stocks": [
                                    {
                                        "code": "603095",
                                        "name": "样例股票",
                                        "continue_num": 4,
                                        "tags": ["总龙头", "一字龙"],
                                    }
                                ],
                            }
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    adapter = DragonEyeAdapter()
    adapter.data_lake_dir = tmp_path
    limit_up, sector, _ = adapter.build_dataframes("2026-04-30")

    assert limit_up["leader_tag"].item() == "总龙头,一字龙"
    assert sector["leader_tag"].item() == "总龙头,一字龙"


def test_dragon_eye_transformer_degrades_missing_numeric_fields():
    frame = DragonEyeTransformer.transform_limit_up(
        "2026-04-30",
        [
            {
                "code": "603095",
                "name": "样例股票",
                "total_market_cap": None,
                "order_amount": 7_691_072.2,
                "tags": "总龙头",
            }
        ],
    )

    row = frame.row(0, named=True)
    assert row["market_cap_yi"] == 0.0
    assert row["order_amount"] == 7_691_072
    assert row["leader_tag"] == "总龙头"


def test_dragon_eye_crawler_retries_empty_trading_day_cache():
    assert StealthCrawler.cached_payload_is_usable(
        "limit_up_filter",
        {"success": True, "data": {}, "note": "empty"},
    ) is False
    assert StealthCrawler.cached_payload_is_usable(
        "limit_up_filter",
        {"success": True, "data": {"stocks": [{"code": "603095"}]}},
    ) is True


def test_factor_precompute_persists_incremental_rows(monkeypatch, tmp_path):
    db_path = str(tmp_path / "lancedb")
    monkeypatch.setattr(Config, "LANCEDB_PATH", db_path)
    db = lancedb.connect(db_path)
    dates = pd.bdate_range("2026-01-01", periods=30)
    daily = pl.DataFrame(
        {
            "trade_date": dates.strftime("%Y-%m-%d").to_list(),
            "stock_code": ["A"] * len(dates),
            "open": [10.0 + i * 0.1 for i in range(len(dates))],
            "high": [10.2 + i * 0.1 for i in range(len(dates))],
            "low": [9.8 + i * 0.1 for i in range(len(dates))],
            "close": [10.1 + i * 0.1 for i in range(len(dates))],
            "volume": [1000.0 + i for i in range(len(dates))],
            "amount": [10000.0 + i for i in range(len(dates))],
            "adj_factor": [1.0] * len(dates),
        }
    ).with_columns(pl.col("trade_date").str.to_date())
    db.create_table("daily_ohlcv", daily.to_arrow())

    start_date = dates[-2].strftime("%Y-%m-%d")
    end_date = dates[-1].strftime("%Y-%m-%d")
    result = FactorPrecomputeService().precompute_all_factors(start_date, end_date)

    assert result.success is True
    assert result.records_computed == 2
    assert "factors" in _table_names(db)
    factors = pl.from_arrow(db.open_table("factors").to_arrow())
    assert factors.height == 2
    assert factors["ma5"].null_count() == 0
