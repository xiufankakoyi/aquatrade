"""Smoke test for the consolidated update entry point.

历史背景：项目早期存在重复更新入口。2026-06-11 数据架构收敛后，**唯一**入口为
``scripts/update/update_market_data_incremental.py``，旧入口已归档。

本测试以 ``scripts/update/update_market_data_incremental.py`` 为目标，验证：
* argparse: 所有支持的 flag 都能解析并落到 ``args`` 中
* target 路由: ``--target`` 决定实际执行的 stage 集合
* ``--only``: 进一步收紧 stage 集合
* ``--dry-run``: 不会真正写入

为避免在沙箱中触发真实 LanceDB / baostock 调用，测试会 monkey-patch 阶段函数。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "update" / "update_market_data_incremental.py"

spec = importlib.util.spec_from_file_location("umdi", SCRIPT_PATH)
umdi = importlib.util.module_from_spec(spec)
sys.modules["umdi"] = umdi
spec.loader.exec_module(umdi)


def _build_stub(name: str, calls: list[str], message: str = "stub"):
    def _stub(*args, **kwargs):
        calls.append(name)
        return umdi.StageResult(
            name=name,
            started_at=umdi._now_text(),
            finished_at=umdi._now_text(),
            success=True,
            message=message,
            duration_seconds=0.001,
        )

    return _stub


def _patch_all_stages(monkeypatch, calls: list[str]):
    """将所有 stage 替换为可记录的桩。"""

    monkeypatch.setattr(umdi, "_stage_daily", _build_stub("daily", calls))
    monkeypatch.setattr(umdi, "_stage_stock_info", _build_stub("stock_info", calls))
    monkeypatch.setattr(umdi, "_stage_trade_status", _build_stub("trade_status", calls))
    monkeypatch.setattr(umdi, "_stage_factors", _build_stub("factors", calls))
    monkeypatch.setattr(umdi, "_stage_matrix_cache", _build_stub("matrix_cache", calls))
    monkeypatch.setattr(umdi, "_stage_sqlite_meta", _build_stub("sqlite_meta", calls))
    monkeypatch.setattr(umdi, "_stage_parquet_snapshot", _build_stub("parquet_snapshot", calls))
    monkeypatch.setattr(umdi, "_stage_health_check", _build_stub("data_health", calls))


def _patch_report_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(umdi, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(umdi, "REPORT_LATEST", tmp_path / "update_report_latest.json")


def test_default_target_is_lancedb(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-05",
    ])

    assert exit_code == 0
    # lancedb target 包含 daily/stock_info/trade_status/factors/data_health
    assert set(calls) == {
        "daily", "stock_info", "trade_status", "factors", "data_health",
    }
    payload = json.loads((tmp_path / "update_report_latest.json").read_text("utf-8"))
    assert payload["status"] == "success"
    assert payload["args"]["target"] == "lancedb"
    assert payload["args"]["start_date"] == "2024-01-01"
    assert payload["args"]["end_date"] == "2024-01-05"
    assert payload["args"]["dry_run"] is False
    assert set(payload["stages"][0]) >= {
        "name", "status", "success", "data_date", "message",
        "rows_added", "rows_updated", "skipped_reason",
    }


def test_target_all_runs_everything_except_parquet(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main([
        "--target", "all",
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-05",
    ])

    assert exit_code == 0
    # all 应该包含 daily/stock_info/trade_status/factors/matrix_cache/data_health，
    # 不包含 parquet_snapshot 与 sqlite_meta
    assert set(calls) == {
        "daily", "stock_info", "trade_status", "factors",
        "matrix_cache", "data_health",
    }


def test_target_matrix_cache_only(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--target", "matrix-cache"])

    assert exit_code == 0
    assert set(calls) == {"matrix_cache", "data_health"}


def test_target_sqlite_meta(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--target", "sqlite-meta"])

    assert exit_code == 0
    assert set(calls) == {"sqlite_meta", "data_health"}


def test_target_parquet_snapshot(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--target", "parquet-snapshot"])

    assert exit_code == 0
    assert set(calls) == {"parquet_snapshot", "data_health"}


def test_only_daily_skips_factors(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--target", "lancedb", "--only", "daily"])

    assert exit_code == 0
    # --only daily 时 factors 不会被执行；其余 lancedb stage 仍执行
    assert "factors" not in calls
    assert "daily" in calls
    assert "data_health" in calls


def test_only_factors_skips_daily(tmp_path, monkeypatch):
    calls: list[str] = []
    _patch_all_stages(monkeypatch, calls)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--target", "lancedb", "--only", "factors"])

    assert exit_code == 0
    assert "daily" not in calls
    assert "factors" in calls
    assert "data_health" in calls


def test_dry_run_flag_propagates(tmp_path, monkeypatch):
    captured: dict[str, bool] = {}

    def _daily(args, start, end):
        captured["daily_dry_run"] = args.dry_run
        return umdi.StageResult(
            name="daily",
            started_at=umdi._now_text(),
            finished_at=umdi._now_text(),
            success=True,
            message="ok",
        )

    def _factors(args, start, end):
        captured["factors_dry_run"] = args.dry_run
        return umdi.StageResult(
            name="factors",
            started_at=umdi._now_text(),
            finished_at=umdi._now_text(),
            success=True,
            message="ok",
        )

    _patch_all_stages(monkeypatch, [])
    monkeypatch.setattr(umdi, "_stage_daily", _daily)
    monkeypatch.setattr(umdi, "_stage_factors", _factors)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main(["--dry-run"])

    assert exit_code == 0
    assert captured == {"daily_dry_run": True, "factors_dry_run": True}
    payload = json.loads((tmp_path / "update_report_latest.json").read_text("utf-8"))
    assert payload["args"]["dry_run"] is True


def test_compact_date_normalized(tmp_path, monkeypatch):
    """``--start-date 20240101`` 必须被规范化为 ISO 形式。"""

    captured: dict[str, str] = {}

    def _daily(args, start, end):
        captured["start"] = start
        captured["end"] = end
        return umdi.StageResult(
            name="daily",
            started_at=umdi._now_text(),
            finished_at=umdi._now_text(),
            success=True,
            message="ok",
        )

    _patch_all_stages(monkeypatch, [])
    monkeypatch.setattr(umdi, "_stage_daily", _daily)
    _patch_report_paths(monkeypatch, tmp_path)

    umdi.main([
        "--start-date", "20240101",
        "--end-date", "20240105",
        "--only", "daily",
    ])

    assert captured == {"start": "2024-01-01", "end": "2024-01-05"}


def test_inverted_range_is_swapped(tmp_path, monkeypatch):
    """``--start-date`` 晚于 ``--end-date`` 时窗口会被自动交换，不报错。"""

    captured: dict[str, str] = {}

    def _daily(args, start, end):
        captured["start"] = start
        captured["end"] = end
        return umdi.StageResult(
            name="daily",
            started_at=umdi._now_text(),
            finished_at=umdi._now_text(),
            success=True,
            message="ok",
        )

    _patch_all_stages(monkeypatch, [])
    monkeypatch.setattr(umdi, "_stage_daily", _daily)
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main([
        "--start-date", "2024-12-01",
        "--end-date", "2024-01-01",
        "--only", "daily",
    ])

    assert exit_code == 0
    # 自动交换为 start <= end
    assert captured == {"start": "2024-01-01", "end": "2024-12-01"}


def test_max_symbols_and_request_delay_recorded(tmp_path, monkeypatch):
    """``--max-symbols`` / ``--request-delay`` 必须落到 args 中并写入报告。"""

    _patch_all_stages(monkeypatch, [])
    _patch_report_paths(monkeypatch, tmp_path)

    exit_code = umdi.main([
        "--max-symbols", "5",
        "--request-delay", "0.25",
        "--target", "lancedb",
    ])

    assert exit_code == 0
    payload = json.loads((tmp_path / "update_report_latest.json").read_text("utf-8"))
    assert payload["args"]["max_symbols"] == 5
    assert payload["args"]["request_delay"] == 0.25


def test_resolve_window_default_range():
    args = umdi.argparse.Namespace(start_date=None, end_date=None)
    start, end = umdi._resolve_window(args)
    # 默认窗口 30 天，end_date 应为今天
    assert start <= end
    from datetime import datetime

    delta = datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")
    assert delta.days >= 29
