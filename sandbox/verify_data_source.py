"""
验证 top3_backtest.py 的数据源

检查：
1. LanceDB 数据库路径
2. 表是否存在
3. 数据量
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb

db_path = Path(__file__).parent.parent / "data" / "lancedb"
print(f"LanceDB 路径: {db_path}")
print(f"路径存在: {db_path.exists()}")

db = lancedb.connect(str(db_path))

print(f"\n可用表: {db.table_names()}")

if 'daily_ohlcv' in db.table_names():
    table = db.open_table("daily_ohlcv")
    print(f"\n[daily_ohlcv] 表信息:")
    print(f"  行数: {table.count_rows():,}")
    
    import polars as pl
    df = pl.from_arrow(table.to_arrow())
    print(f"  列数: {len(df.columns)}")
    print(f"  列名: {df.columns}")
    print(f"  日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
    print(f"  股票数: {df['stock_code'].n_unique()}")

if 'stock_info' in db.table_names():
    table = db.open_table("stock_info")
    print(f"\n[stock_info] 表信息:")
    print(f"  行数: {table.count_rows():,}")

if 'index_daily' in db.table_names():
    table = db.open_table("index_daily")
    print(f"\n[index_daily] 表信息:")
    print(f"  行数: {table.count_rows():,}")
