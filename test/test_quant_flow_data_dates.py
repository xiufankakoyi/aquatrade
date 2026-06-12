from __future__ import annotations

import json
from datetime import date, timedelta

import polars as pl

from config.config import Config
from core.pipeline import quant_flow_pipeline as quant_flow


def test_dragon_eye_uses_latest_complete_evidence_date(tmp_path, monkeypatch):
    data_lake = tmp_path / "data" / "spider_data" / "dragon_eye" / "data_lake"
    partial_dir = data_lake / "2026-06-10"
    partial_dir.mkdir(parents=True)
    complete_dir = data_lake / "2026-04-30"
    complete_dir.mkdir()
    ladder = {
        "dates": [
            {
                "date": "2026-04-30",
                "boards": [
                    {
                        "board": 1,
                        "stocks": [{"code": "000001", "name": "测试股票"}],
                    }
                ],
            }
        ]
    }
    (partial_dir / "ladder_hierarchy_detail.json").write_text(
        json.dumps(ladder, ensure_ascii=False),
        encoding="utf-8",
    )
    (complete_dir / "ladder_hierarchy_detail.json").write_text(
        json.dumps(ladder, ensure_ascii=False),
        encoding="utf-8",
    )
    (complete_dir / "market_sentiment_cycle.json").write_text(
        json.dumps({"success": True, "data": [{"date": "2026-04-30"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(quant_flow, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(Config, "BASE_DIR", str(tmp_path))
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"

    result = pipeline.dragon_eye_summary()

    assert result.status == "warning"
    assert result.data_date == "2026-04-30"
    assert result.data["complete_evidence_date"] == "2026-04-30"
    assert result.data["latest_partial_date"] == "2026-06-10"
    assert result.data["latest_partial_status"]["has_sentiment"] is False


def test_stale_stage_records_reason():
    result = quant_flow.StageResult(
        "market_regime_detect",
        "ok",
        "市场状态",
        {},
        "local_lancedb",
        "本地计算",
        [],
        data_date="2026-04-24",
    )

    quant_flow._downgrade_for_staleness(result, "2026-06-10")

    assert result.status == "warning"
    assert "2026-04-24" in result.stale_reason
    assert "2026-06-10" in result.stale_reason


def test_market_regime_uses_lancedb_component_dates(monkeypatch):
    dates = [date(2026, 5, 11) + timedelta(days=i) for i in range(31)]
    index_frame = pl.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["000300.SH"] * len(dates),
            "name": ["沪深300"] * len(dates),
            "close": [4000.0 + i for i in range(len(dates))],
            "amount": [1000.0 + i * 10 for i in range(len(dates))],
        }
    )
    factors_frame = pl.DataFrame(
        {
            "trade_date": [date(2026, 6, 10)] * 3,
            "stock_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "ret_1d": [0.01, -0.02, 0.0],
        }
    )
    limit_up_frame = pl.DataFrame(
        {
            "trade_date": [date(2026, 6, 10)],
            "stock_code": ["000001.SZ"],
        }
    )

    def fake_read(table_name, *args, **kwargs):
        return {
            "index_daily": index_frame,
            "factors": factors_frame,
            "dragon_eye_limit_up": limit_up_frame,
        }.get(table_name, pl.DataFrame())

    monkeypatch.setattr(quant_flow, "_read_lancedb_table", fake_read)
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"

    result = pipeline.market_regime_detect()

    assert result.status == "ok"
    assert result.source == "local_lancedb"
    assert result.data_date == "2026-06-10"
    assert result.data["breadth"]["rise_count"] == 1
    assert result.data["breadth"]["fall_count"] == 1
    assert result.data["limits"]["limit_up_count"] == 1
    benchmark = next(
        item for item in result.data["index_trends"]
        if item["symbol"] == "000300.SH"
    )
    assert benchmark["return_20d"] is not None


def test_screener_candidates_use_latest_factors(monkeypatch):
    factors_frame = pl.DataFrame(
        {
            "trade_date": [date(2026, 6, 10)] * 3,
            "stock_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "ma5": [12.0, 9.0, 10.0],
            "ma10": [11.0, 10.0, 10.0],
            "ma20": [10.0, 11.0, 10.0],
            "rsi_12": [60.0, 50.0, 80.0],
            "return_5d": [0.03, -0.01, 0.02],
            "return_20d": [0.08, 0.03, 0.04],
            "volatility_20d": [0.02, 0.03, 0.04],
            "ret_1d": [0.01, -0.01, 0.0],
        }
    )
    stock_info_frame = pl.DataFrame(
        {
            "stock_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "name": ["测试一", "测试二", "测试三"],
        }
    )

    def fake_read(table_name, *args, **kwargs):
        return {
            "factors": factors_frame,
            "stock_info": stock_info_frame,
        }.get(table_name, pl.DataFrame())

    monkeypatch.setattr(quant_flow, "_read_lancedb_table", fake_read)
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"

    result = pipeline.stock_screener_candidates()

    assert result.status == "ok"
    assert result.source == "local_lancedb_factors"
    assert result.data_date == "2026-06-10"
    assert result.candidate_count == 1
    assert result.data["candidate_source"] == "lancedb.factors"
    assert result.data["no_candidates"] is False
    assert result.data["filter_rules"]


def test_portfolio_risk_uses_latest_price_valuation_date(tmp_path, monkeypatch):
    pl.DataFrame(
        {
            "id": [1],
            "stock_code": ["000001"],
            "is_active": [True],
        }
    ).write_parquet(tmp_path / "portfolio_positions.parquet")
    daily_frame = pl.DataFrame(
        {
            "trade_date": [date(2026, 6, 10)],
            "stock_code": ["000001.SZ"],
            "close": [10.5],
        }
    )

    monkeypatch.setattr(quant_flow, "PARQUET_DIR", tmp_path)
    monkeypatch.setattr(
        quant_flow,
        "_read_lancedb_table",
        lambda table_name, *args, **kwargs: (
            daily_frame if table_name == "daily_ohlcv" else pl.DataFrame()
        ),
    )
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"

    result = pipeline.portfolio_risk_check()

    assert result.status == "warning"
    assert result.data_date == "2026-06-10"
    assert result.data["valuation_date"] == "2026-06-10"
    assert result.data["valuation_complete"] is False
    assert "shares/quantity" in result.reason


def test_strategy_scan_failure_does_not_fake_data_date(monkeypatch):
    class Factory:
        @staticmethod
        def list_strategies():
            return [{"id": "test"}]

    monkeypatch.setattr(
        "core.strategies.strategy_factory.get_factory",
        lambda: Factory(),
    )
    monkeypatch.setattr(
        quant_flow.QuantFlowPipeline,
        "_resolve_scan_symbols",
        staticmethod(lambda limit: ["000001.SZ"]),
    )
    monkeypatch.setattr(
        "core.portfolio.signal_engine.SignalEngine.generate_signals",
        lambda self, symbols, signal_date=None: (_ for _ in ()).throw(
            RuntimeError("scan failed")
        ),
    )
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"

    result = pipeline.strategy_signal_scan()

    assert result.status == "warning"
    assert result.data_date == ""
    assert result.signal_count == 0
    assert "未完成" in result.stale_reason


def test_final_brief_has_explicit_signal_risk_and_gap_conclusions():
    pipeline = quant_flow.QuantFlowPipeline()
    pipeline.global_latest_trade_date = "2026-06-10"
    pipeline.results = {
        "data_health_check": quant_flow.StageResult(
            "data_health_check", "ok", "数据健康", {}, "local", "ok", [],
            data_date="2026-06-10",
        ),
        "market_regime_detect": quant_flow.StageResult(
            "market_regime_detect", "ok", "指数近20日偏弱，风险偏高",
            {"regime": "指数近20日偏弱", "risk_state": "风险偏高"},
            "local", "ok", [], data_date="2026-06-10",
        ),
        "dragon_eye_summary": quant_flow.StageResult(
            "dragon_eye_summary", "warning", "DragonEye 局部证据",
            {
                "latest_partial_status": {
                    "evidence_date": "2026-06-10",
                    "has_ladder": True,
                    "has_sentiment": False,
                    "missing_parts": ["sentiment", "theme_flow"],
                    "status": "partial",
                },
            },
            "local", "证据不完整", ["missing_components"],
            data_date="2026-06-10",
        ),
        "stock_screener_candidates": quant_flow.StageResult(
            "stock_screener_candidates", "ok", "研究候选 1 条",
            {"candidates": [{"symbol": "000001.SZ", "name": "测试"}], "candidate_count": 1},
            "local", "ok", [], data_date="2026-06-10",
        ),
        "strategy_signal_scan": quant_flow.StageResult(
            "strategy_signal_scan", "warning", "今日无信号",
            {
                "buy": [], "sell": [], "watch": [],
                "blocked_reason": "no_signals_today:rule_not_matched",
            },
            "local", "规则未命中", [], data_date="2026-06-10",
        ),
        "portfolio_risk_check": quant_flow.StageResult(
            "portfolio_risk_check", "warning", "暂无本地持仓记录",
            {"active_position_count": 0, "valuation_complete": False},
            "local", "本地持仓为空", [], data_date="2026-06-10",
        ),
    }

    result = pipeline.final_research_brief()

    assert result.data["signal_conclusion"]["status"] == "无信号"
    assert result.data["signal_conclusion"]["no_signal_reason"]
    assert result.data["portfolio_risk_conclusion"]["status"] == "无本地持仓记录"
    assert result.data["data_gap_conclusion"]["has_gaps"] is True
    assert "无信号" in result.summary
    assert "持仓风险" in result.summary
    assert "数据缺口" in result.summary
