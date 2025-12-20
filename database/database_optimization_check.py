"""Lightweight database integrity checker for the Aquatrade SQLite dataset."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd


class DatabaseCompletenessChecker:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)

        # Expected schema for sanity checks
        self.expected_columns: Dict[str, List[str]] = {
            "stock_info": [
                "stock_code",
                "stock_name",
                "industry",
                "region",
                "list_date",
                "is_st",
                "is_kc",
                "is_cy",
            ],
            "stock_daily": [
                "open",
                "high",
                "low",
                "close",
                "prev_close",
                "change_amount",
                "change_pct",
                "adj_factor",
                "volume",
                "amount",
                "total_mv",
                "float_mv",
                "turnover_rate",
                "turnover_free",
                "volume_ratio",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "dividend_yield",
                "dividend_yield_ttm",
                "total_shares",
                "float_shares",
                "free_float_shares",
                "limit_up",
                "limit_down",
                "stock_code",
                "trade_date",
                "ts_code",
                "ma3_avg_price",
                "ma5_avg_price",
                "ma10_avg_price",
                "ma5",
                "ma10",
                "ma20",
                "volume_ma5",
            ],
        }

    # ----- structure checks -------------------------------------------------
    def check_table_structure(self) -> bool:
        print("=" * 60)
        print("Schema check")
        print("=" * 60)

        cursor = self.conn.cursor()
        all_passed = True

        for table, expected_cols in self.expected_columns.items():
            print(f"\nTable: {table}")
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if not cursor.fetchone():
                print(f"  [FAIL] Table '{table}' is missing")
                all_passed = False
                continue

            cursor.execute(f"PRAGMA table_info({table})")
            actual_columns = [col[1] for col in cursor.fetchall()]

            missing = sorted(set(expected_cols) - set(actual_columns))
            extra = sorted(set(actual_columns) - set(expected_cols))

            if missing:
                print(f"  [FAIL] Missing columns: {missing}")
                all_passed = False
            else:
                print("  [OK] Expected columns present")

            if extra:
                print(f"  [WARN] Extra columns: {extra}")

            print(f"  Expected: {len(expected_cols)}, Actual: {len(actual_columns)}")

        return all_passed

    # ----- data completeness ------------------------------------------------
    def check_data_completeness(self) -> bool:
        print("\n" + "=" * 60)
        print("Data completeness")
        print("=" * 60)

        ok = True

        # stock_info
        print("\n1) stock_info")
        try:
            df_info = pd.read_sql("SELECT * FROM stock_info LIMIT 1000", self.conn)
            if df_info.empty:
                print("  [FAIL] Table is empty")
                ok = False
            else:
                print(f"  [OK] Rows: {len(df_info)}")
                for col in ("stock_code", "stock_name"):
                    nulls = df_info[col].isna().sum()
                    if nulls:
                        print(f"  [FAIL] Nulls in {col}: {nulls}")
                        ok = False
                    else:
                        print(f"  [OK] No nulls in {col}")

                dupes = df_info[df_info.duplicated("stock_code")]
                if not dupes.empty:
                    print(f"  [FAIL] Duplicate stock_code count: {len(dupes)}")
                    ok = False
                else:
                    print("  [OK] No duplicate stock_code values")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"  [FAIL] Failed to read stock_info: {exc}")
            ok = False

        # stock_daily
        print("\n2) stock_daily")
        try:
            df_daily = pd.read_sql("SELECT * FROM stock_daily LIMIT 10000", self.conn)
            if df_daily.empty:
                print("  [FAIL] Table is empty")
                ok = False
            else:
                print(f"  [OK] Sampled rows: {len(df_daily)}")
                print("\n  Null percentage by column:")
                for col in df_daily.columns:
                    null_pct = (df_daily[col].isna().mean()) * 100
                    status = "[OK]" if null_pct < 10 else ("[WARN]" if null_pct < 50 else "[FAIL]")
                    print(f"    {status} {col}: {null_pct:.1f}%")
                    if null_pct > 90 and col in {"stock_code", "trade_date", "close"}:
                        ok = False

                date_stats = pd.read_sql(
                    """
                    SELECT MIN(trade_date) AS min_date,
                           MAX(trade_date) AS max_date,
                           COUNT(DISTINCT trade_date) AS date_count,
                           COUNT(DISTINCT stock_code) AS stock_count
                    FROM stock_daily
                    """,
                    self.conn,
                )
                row = date_stats.iloc[0]
                print(
                    f"\n  Date range: {row['min_date']} -> {row['max_date']} "
                    f"({row['date_count']} trading days)"
                )
                print(f"  Stock count: {row['stock_count']}")

                stock_completeness = pd.read_sql(
                    """
                    SELECT stock_code,
                           COUNT(*) AS record_count,
                           COUNT(DISTINCT trade_date) AS date_count,
                           MIN(trade_date) AS first_date,
                           MAX(trade_date) AS last_date
                    FROM stock_daily
                    GROUP BY stock_code
                    ORDER BY record_count
                    """,
                    self.conn,
                )
                print("\n  Records per stock:")
                print(
                    f"    avg={stock_completeness['record_count'].mean():.1f}, "
                    f"min={stock_completeness['record_count'].min()}, "
                    f"max={stock_completeness['record_count'].max()}"
                )
                low = stock_completeness[stock_completeness["record_count"] < 100]
                if not low.empty:
                    print(f"  [WARN] {len(low)} stocks have fewer than 100 records")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"  [FAIL] Failed to read stock_daily: {exc}")
            ok = False

        return ok

    # ----- technical indicators --------------------------------------------
    def check_technical_indicators(self) -> bool:
        print("\n" + "=" * 60)
        print("Technical indicators")
        print("=" * 60)

        ok = True
        tech_columns = [
            "ma3_avg_price",
            "ma5_avg_price",
            "ma10_avg_price",
            "ma5",
            "ma10",
            "ma20",
            "volume_ma5",
        ]

        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(stock_daily)")
            actual = {col[1] for col in cursor.fetchall()}
            missing = sorted(set(tech_columns) - actual)
            if missing:
                print(f"  [FAIL] Missing indicator columns: {missing}")
                ok = False
            else:
                print("  [OK] Indicator columns exist")

            sample = pd.read_sql(
                """
                SELECT stock_code, trade_date, close,
                       ma3_avg_price, ma5_avg_price, ma10_avg_price,
                       ma5, ma10, ma20, volume_ma5
                FROM stock_daily
                WHERE stock_code IN (SELECT DISTINCT stock_code FROM stock_daily LIMIT 5)
                ORDER BY stock_code, trade_date
                """,
                self.conn,
            )
            if sample.empty:
                print("  [WARN] No sample data to validate indicators")
                return ok

            print("\n  Sampling MA5 calculations (5 stocks):")
            for code in sample["stock_code"].unique():
                data = sample[sample["stock_code"] == code].sort_values("trade_date")
                if len(data) < 5:
                    print(f"    [WARN] {code}: not enough rows to validate")
                    continue
                expected = data.tail(5)["close"].mean()
                stored = data.iloc[-1]["ma5"]
                if stored is None or pd.isna(stored):
                    print(f"    [WARN] {code}: stored MA5 is null")
                elif abs(stored - expected) > 0.01:
                    print(f"    [FAIL] {code}: MA5 mismatch (stored {stored:.4f}, calc {expected:.4f})")
                    ok = False
                else:
                    print(f"    [OK] {code}: MA5 looks correct")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"  [FAIL] Indicator check failed: {exc}")
            ok = False

        return ok

    # ----- report ----------------------------------------------------------
    def generate_summary_report(self) -> bool:
        print("\n" + "=" * 60)
        print("Database integrity report")
        print("=" * 60)

        structure_ok = self.check_table_structure()
        data_ok = self.check_data_completeness()
        tech_ok = self.check_technical_indicators()

        print("\n" + "=" * 60)
        print("Final result")
        print("=" * 60)

        if structure_ok and data_ok and tech_ok:
            print("All checks passed. Database looks good.")
            return True

        print("Issues detected:")
        if not structure_ok:
            print("  - Schema problems")
        if not data_ok:
            print("  - Data completeness problems")
        if not tech_ok:
            print("  - Technical indicator problems")
        return False

    def close(self) -> None:
        self.conn.close()


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir / "stock_data.db"

    if not db_path.exists():
        print(f"错误: 数据库文件 '{db_path}' 不存在")
        return

    checker = DatabaseCompletenessChecker(db_path)
    try:
        success = checker.generate_summary_report()
        if success:
            print("\nDatabase completeness verification passed.")
        else:
            print("\nPlease address the issues reported above.")
    finally:
        checker.close()


if __name__ == "__main__":
    main()
