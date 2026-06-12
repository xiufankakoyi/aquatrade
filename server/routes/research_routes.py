"""Research workbench routes backed by local structured data."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import duckdb
from flask import Blueprint, Response, jsonify, request


research_bp = Blueprint("research_workbench", __name__, url_prefix="/api")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_DIR = PROJECT_ROOT / "data" / "parquet_data"
REPORT_DIR = PROJECT_ROOT / "data" / "reports"


def _success(data: Any, message: str = "ok", **extra: Any):
    payload = {"success": True, "data": data, "message": message}
    payload.update(extra)
    return jsonify(payload)


def _duckdb() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(database=":memory:")


@research_bp.route("/latest_price", methods=["GET"])
def latest_price():
    symbols = [
        item.strip().upper()
        for item in request.args.get("symbols", "").split(",")
        if item.strip()
    ]
    target_date = request.args.get("date")
    if not symbols:
        return _success({}, "请提供 symbols 参数")
    path = PARQUET_DIR / "stock_daily.parquet"
    if not path.exists():
        return _success({}, "暂无本地证据")
    escaped_path = str(path).replace("'", "''")
    values = ",".join("?" for _ in symbols)
    date_clause = "AND CAST(trade_date AS DATE) <= CAST(? AS DATE)" if target_date else ""
    params: list[Any] = symbols[:]
    if target_date:
        params.append(target_date)
    rows = _duckdb().execute(
        f"""
        WITH ranked AS (
          SELECT stock_code, CAST(trade_date AS DATE) AS trade_date, close,
                 ROW_NUMBER() OVER (
                   PARTITION BY stock_code ORDER BY CAST(trade_date AS DATE) DESC
                 ) AS rn
          FROM read_parquet('{escaped_path}')
          WHERE UPPER(stock_code) IN ({values})
          {date_clause}
        )
        SELECT stock_code, trade_date, close FROM ranked WHERE rn = 1
        """,
        params,
    ).fetchall()
    data = {
        str(row[0]): {"price": float(row[2]), "date": str(row[1])}
        for row in rows
        if row[2] is not None
    }
    return _success(
        data,
        "查询完成" if data else "暂无本地证据",
        missing_symbols=[symbol for symbol in symbols if symbol not in data],
    )


@research_bp.route("/stock_posts_by_keyword", methods=["GET"])
def stock_posts_by_keyword():
    keyword = request.args.get("keyword", "").strip()
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    path = PARQUET_DIR / "guba_posts.parquet"
    if not keyword or not path.exists():
        return _success([], "暂无本地证据")
    escaped_path = str(path).replace("'", "''")
    rows = _duckdb().execute(
        f"""
        SELECT symbol, stockbar_name, post_title, post_publish_time,
               post_click_count, post_comment_count, bullish_bearish
        FROM read_parquet('{escaped_path}')
        WHERE post_title IS NOT NULL AND post_title ILIKE ?
        ORDER BY post_publish_time DESC
        LIMIT ?
        """,
        [f"%{keyword}%", limit],
    ).fetchall()
    data = [
        {
            "symbol": row[0],
            "stock_name": row[1],
            "title": row[2],
            "publish_time": str(row[3]) if row[3] is not None else None,
            "click_count": row[4],
            "comment_count": row[5],
            "sentiment": row[6],
            "source": "local_guba_posts",
        }
        for row in rows
    ]
    return _success(data, "查询完成" if data else "暂无本地证据")


def _field_stats(field: str, target_date: str | None) -> dict[str, Any]:
    allowed = {
        "close", "change_pct", "volume", "amount", "total_mv", "float_mv",
        "turnover_rate", "pe", "pe_ttm", "pb", "ps", "dividend_yield",
        "ma5", "ma10", "ma20", "volume_ma5",
    }
    if field not in allowed:
        raise ValueError(f"不支持的字段: {field}")
    path = PARQUET_DIR / "stock_daily.parquet"
    if not path.exists():
        return {}
    escaped_path = str(path).replace("'", "''")
    date_expr = (
        "CAST(? AS DATE)"
        if target_date
        else f"(SELECT MAX(CAST(trade_date AS DATE)) FROM read_parquet('{escaped_path}'))"
    )
    params = [target_date] if target_date else []
    row = _duckdb().execute(
        f"""
        SELECT MIN("{field}"), MAX("{field}"), AVG("{field}"),
               MEDIAN("{field}"), STDDEV_SAMP("{field}"),
               COUNT(*), COUNT("{field}"), CAST(trade_date AS DATE)
        FROM read_parquet('{escaped_path}')
        WHERE CAST(trade_date AS DATE) = {date_expr}
        GROUP BY CAST(trade_date AS DATE)
        """,
        params,
    ).fetchone()
    if not row:
        return {}
    return {
        "field": field,
        "date": str(row[7]),
        "min": row[0],
        "max": row[1],
        "avg": row[2],
        "median": row[3],
        "std": row[4],
        "count": row[5],
        "non_null_count": row[6],
        "source": "local_parquet",
    }


@research_bp.route("/screener/field_stats", methods=["POST"])
def screener_field_stats():
    body = request.get_json(silent=True) or {}
    try:
        data = _field_stats(str(body.get("field") or "close"), body.get("date"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "data": {}}), 400
    return _success(data, "查询完成" if data else "指定日期暂无数据")


@research_bp.route("/screener/export", methods=["POST"])
def screener_export():
    body = request.get_json(silent=True) or {}
    target_date = body.get("date")
    path = PARQUET_DIR / "stock_daily.parquet"
    if not path.exists():
        return jsonify({"success": False, "error": "暂无本地证据"}), 422
    escaped_path = str(path).replace("'", "''")
    date_expr = (
        "CAST(? AS DATE)"
        if target_date
        else f"(SELECT MAX(CAST(trade_date AS DATE)) FROM read_parquet('{escaped_path}'))"
    )
    params = [target_date] if target_date else []
    rows = _duckdb().execute(
        f"""
        SELECT stock_code, CAST(trade_date AS DATE), close, change_pct, volume,
               amount, total_mv, turnover_rate, pe_ttm, pb
        FROM read_parquet('{escaped_path}')
        WHERE CAST(trade_date AS DATE) = {date_expr}
        ORDER BY stock_code
        """,
        params,
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["股票代码", "交易日期", "收盘价", "涨跌幅", "成交量", "成交额",
         "总市值", "换手率", "市盈率TTM", "市净率"]
    )
    writer.writerows(rows)
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=screener.csv"},
    )


@research_bp.route("/benchmark/<code>/equity", methods=["POST"])
def benchmark_equity(code: str):
    body = request.get_json(silent=True) or {}
    start = body.get("start_date") or body.get("start")
    end = body.get("end_date") or body.get("end")
    path = PARQUET_DIR / "benchmark_daily.parquet"
    if not path.exists():
        return _success([], "暂无本地证据")
    escaped_path = str(path).replace("'", "''")
    normalized = code.upper()
    clauses = ["UPPER(code) IN (?, ?)"]
    params: list[Any] = [normalized, normalized.split(".")[0]]
    if start:
        clauses.append("CAST(date AS DATE) >= CAST(? AS DATE)")
        params.append(start)
    if end:
        clauses.append("CAST(date AS DATE) <= CAST(? AS DATE)")
        params.append(end)
    rows = _duckdb().execute(
        f"""
        SELECT CAST(date AS DATE), close
        FROM read_parquet('{escaped_path}')
        WHERE {' AND '.join(clauses)}
        ORDER BY CAST(date AS DATE)
        """,
        params,
    ).fetchall()
    if not rows:
        return _success([], "暂无本地证据")
    base = float(rows[0][1])
    data = [
        {"date": str(row[0]), "equity": float(row[1]) / base if base else None}
        for row in rows
    ]
    return _success(data, "查询完成", benchmark=normalized)


@research_bp.route("/data/health", methods=["GET"])
def data_health():
    from server.services.data_health_service import build_data_health_report

    report = build_data_health_report(write_files=True)
    return _success(report, report["message"])


@research_bp.route("/data/matrix-cache/rebuild", methods=["POST"])
def rebuild_matrix_cache():
    from scripts.update.update_market_data_incremental import parse_args_with, run

    payload = request.get_json(silent=True) or {}
    argv = ["--target", "matrix-cache"]
    if payload.get("start_date"):
        argv.extend(["--start-date", str(payload["start_date"])])
    if payload.get("end_date"):
        argv.extend(["--end-date", str(payload["end_date"])])
    report = run(parse_args_with(argv))
    matrix_stage = next(
        (item for item in report.get("stages", []) if item.get("name") == "matrix_cache"),
        {},
    )
    if matrix_stage.get("status") == "failed":
        return jsonify(
            {
                "success": False,
                "data": report,
                "error": matrix_stage.get("message") or "回测缓存重建失败",
            }
        ), 500
    return _success(report, matrix_stage.get("message") or "回测缓存重建完成")


@research_bp.route("/quant-flow/latest", methods=["GET"])
def quant_flow_latest():
    path = REPORT_DIR / "quant_flow_latest.json"
    if not path.exists():
        return _success({}, "尚未运行 QuantFlow")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return jsonify({"success": False, "data": {}, "error": str(exc)}), 500
    return _success(data, "读取完成")


@research_bp.route("/quant-flow/run", methods=["POST"])
def quant_flow_run():
    from core.pipeline.quant_flow_pipeline import QuantFlowPipeline

    report = QuantFlowPipeline().run(write_files=True)
    return _success(report, "QuantFlow 运行完成")
