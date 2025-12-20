"""
辅助脚本：排查 stock_daily 在某些交易日异常膨胀或重复数据导致的慢查询

用法示例：
    python tools/inspect_stock_daily_slow_dates.py --date 2024-01-04
    python tools/inspect_stock_daily_slow_dates.py --start 2024-01-01 --end 2024-03-01
"""

import argparse
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import Config
from database.db_utils import apply_performance_pragmas


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
    apply_performance_pragmas(conn, read_only=True)
    return conn


def parse_date_range(args: argparse.Namespace) -> Tuple[str, str]:
    if args.date:
        return args.date, args.date
    if args.start and args.end:
        return args.start, args.end
    raise ValueError("请提供 --date 或 --start 与 --end")


def inspect_range(conn: sqlite3.Connection, start: str, end: str) -> None:
    cursor = conn.execute(
        """
        SELECT trade_date, COUNT(*) AS cnt
        FROM stock_daily
        WHERE trade_date BETWEEN ? AND ?
        GROUP BY trade_date
        ORDER BY trade_date
        """,
        (start, end),
    )
    rows = cursor.fetchall()
    print("\n交易日记录数")
    header = f"{'日期':12} | {'记录数':>10}"
    print(header)
    print("-" * len(header))
    for trade_date, cnt in rows:
        print(f"{trade_date:12} | {cnt:10d}")


def inspect_duplicates(conn: sqlite3.Connection, date: str, limit: int = 50) -> None:
    cursor = conn.execute(
        """
        SELECT stock_code, COUNT(*) AS cnt
        FROM stock_daily
        WHERE trade_date = ?
        GROUP BY stock_code
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (date, limit),
    )
    rows = cursor.fetchall()
    print(f"\n{date} 重复行 TOP {limit}")
    if not rows:
        print("未发现重复行")
        return
    header = f"{'stock_code':12} | {'重复条数':>8}"
    print(header)
    print("-" * len(header))
    for code, cnt in rows:
        print(f"{code:12} | {cnt:8d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="检查 stock_daily 异常膨胀/重复数据的辅助脚本")
    parser.add_argument("--date", help="单个交易日 YYYY-MM-DD")
    parser.add_argument("--start", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    args = parser.parse_args()

    start, end = parse_date_range(args)

    conn = connect_db()
    try:
        inspect_range(conn, start, end)
        if start == end:
            inspect_duplicates(conn, start)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
