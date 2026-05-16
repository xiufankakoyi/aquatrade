from __future__ import annotations

import pandas as pd

from server.data_sync.sync_industry_data import IndustryDataSync


class FakeRegistry:
    def __init__(self) -> None:
        self.logs = []

    def get_realtime_quotes(self, trade_date=None):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-05-16",
                    "symbol": "300308.SZ",
                    "stock_name": "中际旭创",
                    "pct_chg": 6.2,
                    "close": 100,
                    "high": 105,
                    "low": 96,
                    "open": 98,
                    "amount": 1.2e10,
                    "volume": 1000000,
                    "turnover_rate": 3.2,
                    "volume_ratio": 1.5,
                    "total_market_cap": 1.0e11,
                    "float_market_cap": 9.0e10,
                    "provider": "fake",
                    "updated_at": "2026-05-16 15:00:00",
                },
                {
                    "trade_date": "2026-05-16",
                    "symbol": "688498.SH",
                    "stock_name": "源杰科技",
                    "pct_chg": 10.0,
                    "close": 80,
                    "high": 80,
                    "low": 72,
                    "open": 73,
                    "amount": 2.5e9,
                    "volume": 500000,
                    "turnover_rate": 8.0,
                    "volume_ratio": 2.2,
                    "total_market_cap": 2.0e10,
                    "float_market_cap": 1.4e10,
                    "provider": "fake",
                    "updated_at": "2026-05-16 15:00:00",
                },
            ]
        )

    def get_daily_bars(self, start_date, end_date, symbols=None):
        return pd.DataFrame()

    def get_concept_boards(self, trade_date=None):
        return pd.DataFrame(
            [
                {"trade_date": "2026-05-16", "board_code": "BK1", "board_name": "光模块", "board_type": "concept", "pct_chg": 5.1, "amount": 8e10, "stock_count": 50, "provider": "fake", "updated_at": "2026-05-16 15:00:00"},
                {"trade_date": "2026-05-16", "board_code": "BK2", "board_name": "光芯片", "board_type": "concept", "pct_chg": 7.0, "amount": 3e10, "stock_count": 20, "provider": "fake", "updated_at": "2026-05-16 15:00:00"},
                {"trade_date": "2026-05-16", "board_code": "BK3", "board_name": "磷化铟", "board_type": "concept", "pct_chg": 4.0, "amount": 1e10, "stock_count": 8, "provider": "fake", "updated_at": "2026-05-16 15:00:00"},
            ]
        )

    def get_concept_board_members(self, board_code_or_name, trade_date=None, board_name=None):
        members = {
            "BK1": [("300308.SZ", "中际旭创"), ("300394.SZ", "天孚通信")],
            "BK2": [("688498.SH", "源杰科技")],
            "BK3": [("688498.SH", "源杰科技")],
        }
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-05-16",
                    "board_code": board_code_or_name,
                    "board_name": board_name,
                    "symbol": symbol,
                    "stock_name": name,
                    "pct_chg": 0,
                    "amount": 0,
                    "provider": "fake",
                    "updated_at": "2026-05-16 15:00:00",
                }
                for symbol, name in members.get(board_code_or_name, [])
            ]
        )

    def get_limit_up_pool(self, trade_date):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-05-16",
                    "symbol": "688498.SH",
                    "stock_name": "源杰科技",
                    "pct_chg": 10,
                    "close": 80,
                    "amount": 2.5e9,
                    "first_limit_time": "09:45",
                    "last_limit_time": "14:55",
                    "open_count": 1,
                    "limit_up_reason": "光芯片",
                    "consecutive_limit_count": 2,
                    "provider": "fake",
                    "updated_at": "2026-05-16 15:00:00",
                }
            ]
        )

    def get_board_fund_flow(self, trade_date):
        return pd.DataFrame()

    def get_stock_fund_flow(self, trade_date):
        return pd.DataFrame(
            [
                {"trade_date": "2026-05-16", "symbol": "688498.SH", "stock_name": "源杰科技", "main_net_inflow": 2e8, "super_large_net_inflow": 1e8, "large_net_inflow": 1e8, "small_net_inflow": -2e7, "pct_chg": 10, "provider": "fake", "updated_at": "2026-05-16 15:00:00"}
            ]
        )

    def get_stock_basic_info(self, symbols=None):
        return pd.DataFrame(
            [
                {"symbol": "300308.SZ", "stock_name": "中际旭创", "industry": "光模块", "area": "", "list_date": "", "business_scope": "光模块", "main_business": "光模块", "provider": "fake", "updated_at": "2026-05-16 15:00:00"},
                {"symbol": "688498.SH", "stock_name": "源杰科技", "industry": "光芯片", "area": "", "list_date": "", "business_scope": "磷化铟 光芯片", "main_business": "光芯片", "provider": "fake", "updated_at": "2026-05-16 15:00:00"},
            ]
        )

    def log_frame(self):
        return pd.DataFrame(
            [{"trade_date": "2026-05-16", "method": "fake", "context": "", "provider_used": "fake", "success": True, "row_count": 1, "fetch_time": 0.01, "error_message": "", "updated_at": "2026-05-16 15:00:00"}]
        )


def test_industry_auto_update_generates_candidates_without_manual_csv(monkeypatch, tmp_path):
    captured = {}
    sync = IndustryDataSync(output_dir=tmp_path, registry=FakeRegistry())

    def capture_write(filename, df, columns):
        captured[filename] = df.copy()

    monkeypatch.setattr(sync, "_write", capture_write)
    summary = sync.sync_all(chain_id="optical_communication", trade_date="2026-05-16")

    candidates = captured["industry_node_candidates.parquet"]
    metrics = captured["industry_node_metrics.parquet"]
    assert summary["status"] == "success"
    assert not candidates.empty
    assert {"optical_module", "optical_chip", "indium_phosphide"} <= set(candidates["node_id"])
    assert "system_relevance_score" not in candidates.columns
    assert metrics["hot_score"].max() > 0
