"""Seven-stage local research workflow.

The pipeline only uses local structured evidence. It does not place orders and
does not manufacture conclusions when a source is missing.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "data" / "reports"
PARQUET_DIR = PROJECT_ROOT / "data" / "parquet_data"


@dataclass
class StageResult:
    stage: str
    status: str
    summary: str
    data: Any
    source: str
    reason: str
    errors: list[str]


class QuantFlowPipeline:
    stage_names = [
        "data_health_check",
        "market_regime_detect",
        "dragon_eye_summary",
        "stock_screener_candidates",
        "strategy_signal_scan",
        "portfolio_risk_check",
        "final_research_brief",
    ]

    def __init__(self) -> None:
        self.results: dict[str, StageResult] = {}

    def _run_stage(
        self, name: str, handler: Callable[[], StageResult]
    ) -> StageResult:
        try:
            result = handler()
        except Exception as exc:
            result = StageResult(
                name,
                "error",
                "阶段执行失败",
                {},
                "local_structured_data",
                str(exc),
                [str(exc)],
            )
        self.results[name] = result
        return result

    def data_health_check(self) -> StageResult:
        from server.services.data_health_service import build_data_health_report

        report = build_data_health_report(write_files=True)
        return StageResult(
            "data_health_check",
            "ok" if report["status"] == "ok" else "warning",
            f"数据健康状态：{report['status']}",
            report,
            "local_structured_data",
            report["message"],
            [],
        )

    def market_regime_detect(self) -> StageResult:
        path = PARQUET_DIR / "benchmark_daily.parquet"
        if not path.exists():
            return StageResult(
                "market_regime_detect", "skipped", "暂无本地证据", {},
                "local_parquet", "缺少 benchmark_daily.parquet", [],
            )
        import duckdb

        escaped = str(path).replace("'", "''")
        rows = duckdb.connect(database=":memory:").execute(
            f"""
            SELECT CAST(date AS DATE) AS d, close
            FROM read_parquet('{escaped}')
            WHERE code IN ('000300.SH', '000300', 'HS300')
              AND close IS NOT NULL
            ORDER BY d DESC
            LIMIT 21
            """
        ).fetchall()
        if len(rows) < 2:
            return StageResult(
                "market_regime_detect", "skipped", "暂无本地证据", {},
                "local_parquet", "基准历史数据不足", [],
            )
        rows.reverse()
        start_close = float(rows[0][1])
        end_close = float(rows[-1][1])
        change = (end_close / start_close - 1.0) if start_close else None
        if change is None:
            label = "unknown"
        elif change > 0.03:
            label = "近20期偏强"
        elif change < -0.03:
            label = "近20期偏弱"
        else:
            label = "近20期震荡"
        return StageResult(
            "market_regime_detect",
            "ok",
            label,
            {
                "benchmark": "000300.SH",
                "start_date": str(rows[0][0]),
                "end_date": str(rows[-1][0]),
                "period_return": change,
                "regime": label,
            },
            "local_parquet",
            "根据本地基准收盘价客观计算，不构成投资建议",
            [],
        )

    def dragon_eye_summary(self) -> StageResult:
        base = PROJECT_ROOT / "data" / "spider_data" / "dragon_eye" / "data_lake"
        date_dirs = sorted((item for item in base.glob("*") if item.is_dir()), reverse=True)
        if not date_dirs:
            return StageResult(
                "dragon_eye_summary", "skipped", "暂无本地证据", {},
                "local_spider", "未找到 DragonEye 日期目录", [],
            )
        latest = date_dirs[0]
        evidence: dict[str, Any] = {}
        errors: list[str] = []
        for name in ("market_sentiment_cycle", "sector_heat_stats", "risk_monitor_list"):
            path = latest / f"{name}.json"
            if not path.exists():
                continue
            try:
                evidence[name] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        if not evidence:
            return StageResult(
                "dragon_eye_summary", "warning", "暂无本地证据", {},
                "local_spider", f"{latest.name} 目录没有可解析证据", errors,
            )
        return StageResult(
            "dragon_eye_summary",
            "warning" if errors else "ok",
            f"读取 DragonEye 本地证据，日期 {latest.name}",
            {"date": latest.name, "evidence": evidence},
            "local_spider",
            "仅展示本地结构化证据",
            errors,
        )

    def stock_screener_candidates(self) -> StageResult:
        path = PARQUET_DIR / "watchlist.parquet"
        if not path.exists():
            return StageResult(
                "stock_screener_candidates", "skipped", "暂无本地证据", [],
                "local_watchlist", "缺少 watchlist.parquet", [],
            )
        import duckdb

        escaped = str(path).replace("'", "''")
        rows = duckdb.connect(database=":memory:").execute(
            f"""
            SELECT stock_code, stock_name, tags
            FROM read_parquet('{escaped}')
            WHERE COALESCE(is_active, true)
            ORDER BY stock_code
            LIMIT 100
            """
        ).fetchall()
        candidates = [
            {"symbol": row[0], "name": row[1], "tags": row[2]}
            for row in rows
        ]
        if not candidates:
            return StageResult(
                "stock_screener_candidates", "skipped", "暂无本地证据", [],
                "local_watchlist", "本地自选研究池为空", [],
            )
        return StageResult(
            "stock_screener_candidates",
            "ok",
            f"本地自选研究池共 {len(candidates)} 条",
            candidates,
            "local_watchlist",
            "研究候选来自本地自选池，不代表投资建议",
            [],
        )

    def strategy_signal_scan(self) -> StageResult:
        report_files = sorted(
            (PROJECT_ROOT / "data" / "backtest_results").glob("*.parquet"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not report_files:
            return StageResult(
                "strategy_signal_scan", "skipped", "暂无本地证据", [],
                "local_backtest_results", "没有本地回测结果", [],
            )
        latest = report_files[0]
        return StageResult(
            "strategy_signal_scan",
            "warning",
            "检测到本地回测结果，但未配置可执行信号扫描器",
            {"latest_backtest_file": str(latest), "signals": []},
            "local_backtest_results",
            "未生成或编造策略信号",
            [],
        )

    def portfolio_risk_check(self) -> StageResult:
        path = PARQUET_DIR / "portfolio_positions.parquet"
        if not path.exists():
            return StageResult(
                "portfolio_risk_check", "skipped", "暂无本地证据", {},
                "local_portfolio", "缺少 portfolio_positions.parquet", [],
            )
        import duckdb

        escaped = str(path).replace("'", "''")
        rows = duckdb.connect(database=":memory:").execute(
            f"""
            SELECT stock_code
            FROM read_parquet('{escaped}')
            WHERE COALESCE(is_active, true)
            """
        ).fetchall()
        symbols = sorted({str(row[0]) for row in rows if row[0]})
        return StageResult(
            "portfolio_risk_check",
            "ok" if symbols else "warning",
            f"当前本地持仓记录 {len(symbols)} 条",
            {
                "active_position_count": len(symbols),
                "symbols": symbols,
                "checks": ["记录完整性"],
            },
            "local_portfolio",
            "仅做数据完整性检查，未输出仓位或交易建议",
            [],
        )

    def final_research_brief(self) -> StageResult:
        health = self.results.get("data_health_check")
        failed = [
            name
            for name, result in self.results.items()
            if result.status in {"error", "skipped"}
        ]
        incomplete = bool(
            failed or not health or health.status in {"warning", "error"}
        )
        summary = (
            "数据或模块不完整，禁止生成真实交易计划。"
            if incomplete
            else "本地研究流水线已完成；结果仅用于研究复核，不构成投资建议。"
        )
        return StageResult(
            "final_research_brief",
            "warning" if incomplete else "ok",
            summary,
            {
                "data_health": self.results.get("data_health_check").summary
                if self.results.get("data_health_check") else "未运行",
                "market_regime": self.results.get("market_regime_detect").summary
                if self.results.get("market_regime_detect") else "未运行",
                "strong_directions": self.results.get("dragon_eye_summary").data
                if self.results.get("dragon_eye_summary") else {},
                "research_candidates": self.results.get("stock_screener_candidates").data
                if self.results.get("stock_screener_candidates") else [],
                "strategy_signals": self.results.get("strategy_signal_scan").data
                if self.results.get("strategy_signal_scan") else [],
                "portfolio_risk": self.results.get("portfolio_risk_check").data
                if self.results.get("portfolio_risk_check") else {},
                "operational_note": summary,
                "failed_or_skipped_modules": failed,
            },
            "quant_flow_pipeline",
            "汇总前序阶段，不添加外部或随机结论",
            [],
        )

    def run(self, write_files: bool = True) -> dict[str, Any]:
        started_at = datetime.now().astimezone()
        handlers = [
            self.data_health_check,
            self.market_regime_detect,
            self.dragon_eye_summary,
            self.stock_screener_candidates,
            self.strategy_signal_scan,
            self.portfolio_risk_check,
            self.final_research_brief,
        ]
        for name, handler in zip(self.stage_names, handlers):
            self._run_stage(name, handler)
        report = {
            "run_at": started_at.isoformat(timespec="seconds"),
            "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": "local_structured_data",
            "status": "error" if any(
                item.status == "error" for item in self.results.values()
            ) else (
                "warning" if any(
                    item.status in {"warning", "skipped"}
                    for item in self.results.values()
                ) else "ok"
            ),
            "stages": [asdict(self.results[name]) for name in self.stage_names],
            "final_brief": asdict(self.results["final_research_brief"]),
        }
        if write_files:
            self.write_reports(report)
        return report

    @staticmethod
    def write_reports(report: dict[str, Any]) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "quant_flow_latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# QuantFlow 五分钟投研流水线报告",
            "",
            f"- 运行时间：{report['run_at']}",
            f"- 总体状态：`{report['status']}`",
            f"- 数据来源：`{report['source']}`",
            "",
            "## 阶段结果",
            "",
            "| 阶段 | 状态 | 摘要 | 原因 |",
            "| --- | --- | --- | --- |",
        ]
        for stage in report["stages"]:
            lines.append(
                f"| {stage['stage']} | {stage['status']} | "
                f"{stage['summary']} | {stage['reason']} |"
            )
        final_data = report["final_brief"]["data"]
        lines.extend(
            [
                "",
                "## 最终简报",
                "",
                f"- 数据健康：{final_data.get('data_health', '未运行')}",
                f"- 市场状态：{final_data.get('market_regime', '未运行')}",
                f"- 强势方向：{json.dumps(final_data.get('strong_directions', {}), ensure_ascii=False)}",
                f"- 研究候选：{json.dumps(final_data.get('research_candidates', []), ensure_ascii=False)}",
                f"- 策略信号：{json.dumps(final_data.get('strategy_signals', []), ensure_ascii=False)}",
                f"- 持仓风险：{json.dumps(final_data.get('portfolio_risk', {}), ensure_ascii=False)}",
                f"- 今日操作说明：{final_data.get('operational_note', '')}",
                f"- 失败或跳过模块：{', '.join(final_data.get('failed_or_skipped_modules', [])) or '无'}",
            ]
        )
        (REPORT_DIR / "quant_flow_latest.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    print(
        json.dumps(
            QuantFlowPipeline().run(write_files=True),
            ensure_ascii=False,
            indent=2,
        )
    )
