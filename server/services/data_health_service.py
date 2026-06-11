"""Local data health inspection and report generation."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"


@dataclass
class DatasetHealth:
    name: str
    path: str
    exists: bool
    row_count: int | None
    earliest_date: str | None
    latest_date: str | None
    field_count: int | None
    missing_required_fields: list[str]
    missing_dates: list[str]
    source: str
    status: str
    message: str


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _weekday_gaps(values: Iterable[Any], limit: int = 100) -> list[str]:
    dates: set[date] = set()
    for value in values:
        text = _date_text(value)
        if not text:
            continue
        try:
            dates.add(datetime.fromisoformat(text).date())
        except ValueError:
            continue
    if len(dates) < 2:
        return []
    current = min(dates)
    end = max(dates)
    missing: list[str] = []
    while current <= end and len(missing) < limit:
        if current.weekday() < 5 and current not in dates:
            missing.append(current.isoformat())
        current += timedelta(days=1)
    return missing


def _inspect_sqlite(path: Path) -> DatasetHealth:
    required = {"stock_daily": {"stock_code", "trade_date", "close"}}
    if not path.exists():
        return DatasetHealth(
            "sqlite", str(path), False, 0, None, None, 0,
            sorted(required["stock_daily"]), [], "local_sqlite", "error",
            "数据库文件不存在",
        )
    row_count = 0
    field_count = 0
    earliest = None
    latest = None
    missing_fields: list[str] = []
    message = "本地 SQLite 可访问"
    status = "ok"
    try:
        with sqlite3.connect(path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "stock_daily" not in tables:
                missing_fields = sorted(required["stock_daily"])
                status = "warning"
                message = "缺少 stock_daily 表"
            else:
                fields = {
                    row[1] for row in conn.execute("PRAGMA table_info(stock_daily)")
                }
                field_count = len(fields)
                missing_fields = sorted(required["stock_daily"] - fields)
                row_count = int(
                    conn.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
                )
                if "trade_date" in fields:
                    earliest, latest = conn.execute(
                        "SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily"
                    ).fetchone()
                if missing_fields or row_count == 0:
                    status = "warning"
                    message = "SQLite 数据为空或缺少必需字段"
    except Exception as exc:
        status = "error"
        message = f"SQLite 检查失败: {exc}"
    return DatasetHealth(
        "sqlite",
        str(path),
        True,
        row_count,
        _date_text(earliest),
        _date_text(latest),
        field_count,
        missing_fields,
        [],
        "local_sqlite",
        status,
        message,
    )


def _inspect_parquet(path: Path) -> DatasetHealth:
    required = {"stock_code", "trade_date", "open", "high", "low", "close"}
    if not path.exists():
        return DatasetHealth(
            "parquet", str(path), False, 0, None, None, 0,
            sorted(required), [], "local_parquet", "error", "Parquet 目录不存在",
        )
    files = sorted(path.glob("*.parquet"))
    primary = path / "stock_daily.parquet"
    target = primary if primary.exists() else (files[0] if files else None)
    if target is None:
        return DatasetHealth(
            "parquet", str(path), True, 0, None, None, 0,
            sorted(required), [], "local_parquet", "warning", "目录中没有 Parquet 文件",
        )

    row_count = 0
    field_count = 0
    earliest = None
    latest = None
    missing_dates: list[str] = []
    missing_fields: list[str] = []
    status = "ok"
    message = f"主数据文件: {target.name}"
    try:
        import pyarrow.parquet as pq

        metadata = pq.read_metadata(target)
        row_count = metadata.num_rows
        fields = set(metadata.schema.names)
        field_count = len(fields)
        missing_fields = sorted(required - fields)
        date_field = "trade_date" if "trade_date" in fields else (
            "date" if "date" in fields else None
        )
        if date_field and row_count:
            import duckdb

            escaped = str(target).replace("'", "''")
            rows = duckdb.connect(database=":memory:").execute(
                f'SELECT DISTINCT CAST("{date_field}" AS DATE) AS d '
                f"FROM read_parquet('{escaped}') WHERE \"{date_field}\" IS NOT NULL "
                "ORDER BY d"
            ).fetchall()
            normalized = [_date_text(row[0]) for row in rows]
            if normalized:
                earliest = normalized[0]
                latest = normalized[-1]
                missing_dates = _weekday_gaps(normalized)
        if missing_fields or row_count == 0:
            status = "warning"
            message = "Parquet 数据为空或缺少必需字段"
    except Exception as exc:
        status = "error"
        message = f"Parquet 检查失败: {exc}"
    return DatasetHealth(
        "parquet",
        str(path),
        True,
        row_count,
        earliest,
        latest,
        field_count,
        missing_fields,
        missing_dates,
        "local_parquet",
        status,
        message,
    )


def _inspect_lancedb(path: Path) -> DatasetHealth:
    required = {"stock_code", "trade_date", "close"}
    if not path.exists():
        return DatasetHealth(
            "lancedb", str(path), False, 0, None, None, 0,
            sorted(required), [], "local_lancedb", "error", "LanceDB 目录不存在",
        )
    row_count = 0
    field_count = 0
    earliest = None
    latest = None
    missing_fields: list[str] = []
    status = "unknown"
    message = "LanceDB 目录存在，未读取到可用表"
    try:
        import lancedb
        import pyarrow.compute as pc

        db = lancedb.connect(str(path))
        table_names = list(db.list_tables().tables)
        target_name = "daily_ohlcv" if "daily_ohlcv" in table_names else (
            table_names[0] if table_names else None
        )
        if target_name:
            table = db.open_table(target_name)
            fields = {field.name for field in table.schema}
            field_count = len(fields)
            missing_fields = sorted(required - fields)
            row_count = int(table.count_rows())
            if "trade_date" in fields and row_count:
                dates = (
                    table.to_lance()
                    .scanner(columns=["trade_date"])
                    .to_table()
                    .column("trade_date")
                )
                earliest = _date_text(pc.min(dates).as_py())
                latest = _date_text(pc.max(dates).as_py())
            status = "warning" if missing_fields or row_count == 0 else "ok"
            message = f"LanceDB 表: {target_name}"
    except Exception as exc:
        status = "warning"
        message = f"LanceDB 元数据读取失败: {exc}"
    return DatasetHealth(
        "lancedb",
        str(path),
        True,
        row_count,
        earliest,
        latest,
        field_count,
        missing_fields,
        [],
        "local_lancedb",
        status,
        message,
    )


def _inspect_directory(name: str, path: Path, source: str) -> DatasetHealth:
    exists = path.exists()
    file_count = 0
    if exists:
        try:
            file_count = sum(1 for item in path.rglob("*") if item.is_file())
        except OSError:
            file_count = 0
    return DatasetHealth(
        name,
        str(path),
        exists,
        file_count,
        None,
        None,
        None,
        [],
        [],
        source,
        "ok" if exists and file_count else ("warning" if exists else "unknown"),
        "目录文件数作为 row_count" if exists else "目录不存在",
    )


def build_data_health_report(write_files: bool = True) -> dict[str, Any]:
    datasets = [
        _inspect_sqlite(DATA_DIR / "database" / "stock_data.db"),
        _inspect_lancedb(DATA_DIR / "lancedb"),
        _inspect_parquet(DATA_DIR / "parquet_data"),
        _inspect_directory(
            "factor_matrix_cache", DATA_DIR / "factor_matrix_cache", "local_cache"
        ),
        _inspect_directory("matrix_cache", DATA_DIR / "matrix_cache", "local_cache"),
        _inspect_directory("spider_data", DATA_DIR / "spider_data", "local_spider"),
        _inspect_directory("industry", DATA_DIR / "industry", "local_structured_evidence"),
    ]
    statuses = {item.status for item in datasets}
    overall = "error" if "error" in statuses else (
        "warning" if statuses & {"warning", "unknown"} else "ok"
    )
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": overall,
        "source": "local_structured_data",
        "message": "数据健康检查完成",
        "datasets": [asdict(item) for item in datasets],
    }
    if write_files:
        write_data_health_reports(report)
    return report


def write_data_health_reports(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "data_health_latest.json"
    md_path = REPORT_DIR / "data_health_latest.md"
    map_path = PROJECT_ROOT / "DATA_MAP.generated.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows = [
        "# 数据健康报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 总体状态：`{report['status']}`",
        f"- 数据来源：`{report['source']}`",
        "",
        "| 数据集 | 状态 | 行数/文件数 | 最早日期 | 最新日期 | 缺失字段 | 缺失日期数 |",
        "| --- | --- | ---: | --- | --- | --- | ---: |",
    ]
    for item in report["datasets"]:
        rows.append(
            "| {name} | {status} | {rows} | {earliest} | {latest} | {missing} | {gaps} |".format(
                name=item["name"],
                status=item["status"],
                rows=item["row_count"] if item["row_count"] is not None else "N/A",
                earliest=item["earliest_date"] or "N/A",
                latest=item["latest_date"] or "N/A",
                missing=", ".join(item["missing_required_fields"]) or "无",
                gaps=len(item["missing_dates"]),
            )
        )
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    map_rows = [
        "# AquaTrade 数据地图（自动生成）",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "| 数据集 | 路径 | 来源 | 状态 | 字段数 |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for item in report["datasets"]:
        map_rows.append(
            f"| {item['name']} | `{item['path']}` | `{item['source']}` | "
            f"`{item['status']}` | {item['field_count'] if item['field_count'] is not None else 'N/A'} |"
        )
    map_path.write_text("\n".join(map_rows) + "\n", encoding="utf-8")
