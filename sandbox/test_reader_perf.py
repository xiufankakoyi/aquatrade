"""测试封装接口性能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import polars as pl
import lancedb

project_root = Path(__file__).parent.parent
db_path = project_root / "data" / "lancedb"

# 方式1：原生 API 全量读取
print("[方式1] 原生 API 全量读取...")
t1 = time.time()
db = lancedb.connect(str(db_path))
table = db.open_table("daily_ohlcv")
daily_df = pl.from_arrow(table.to_arrow())
daily_df = daily_df.filter(
    (pl.col('trade_date').cast(pl.Utf8) >= '2023-01-01') &
    (pl.col('trade_date').cast(pl.Utf8) <= '2024-12-31')
)
print(f"  耗时: {time.time() - t1:.2f}s, 行数: {len(daily_df)}, 列数: {len(daily_df.columns)}")

# 方式2：封装接口（指定列）
print("\n[方式2] 封装接口（指定列）...")
t1 = time.time()
from data_svc.storage.unified_reader import get_lancedb_reader
reader = get_lancedb_reader(str(db_path))
daily_df2 = reader.read(
    symbols=None,
    start_date="2023-01-01",
    end_date="2024-12-31",
    fields=['stock_code', 'trade_date', 'close', 'volume']
)
print(f"  耗时: {time.time() - t1:.2f}s, 行数: {len(daily_df2)}, 列数: {len(daily_df2.columns)}")

# 方式3：封装接口（全量列）
print("\n[方式3] 封装接口（全量列）...")
t1 = time.time()
daily_df3 = reader.read_all_columns(
    start_date="2023-01-01",
    end_date="2024-12-31"
)
print(f"  耗时: {time.time() - t1:.2f}s, 行数: {len(daily_df3)}, 列数: {len(daily_df3.columns)}")
