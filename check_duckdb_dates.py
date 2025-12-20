import os
import duckdb
from pathlib import Path

parquet_dir = os.getenv("PARQUET_DIR", "parquet_data")
daily_path = Path(parquet_dir) / "stock_daily.parquet"

print(f"PARQUET_DIR = {parquet_dir}")
print(f"stock_daily path = {daily_path}")

if not daily_path.exists():
    print("[ERROR] stock_daily.parquet 不存在，请检查 PARQUET_DIR")
    raise SystemExit(1)

conn = duckdb.connect()
daily_str = str(daily_path).replace("\\", "/")
conn.execute(
    f"CREATE OR REPLACE VIEW stock_daily AS SELECT * FROM parquet_scan('{daily_str}')"
)

print("\n[INFO] 全部数据的日期范围与总行数:")
print(conn.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM stock_daily").fetchall())

print("\n[INFO] 2024-12-04 ~ 2025-11-07 区间的行数:")
print(
    conn.execute(
        "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM stock_daily WHERE trade_date BETWEEN '2024-12-04' AND '2025-11-07'"
    ).fetchall()
)

