"""
调试2026年数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
import polars as pl
import numpy as np

db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
table = db.open_table("daily_ohlcv")
df = pl.from_arrow(table.to_arrow())

# 检查日期格式
print("原始日期示例:")
for i, d in enumerate(df['trade_date'][:5]):
    print(f"  {i}: {d} (type: {type(d)})")

# 转换日期
df = df.with_columns(pl.col('trade_date').cast(pl.Datetime).dt.strftime('%Y-%m-%d').alias('date_str'))

# 检查2026年数据
df_2026 = df.filter(pl.col('date_str') >= '2026-01-01')
print(f"\n2026年数据行数: {len(df_2026)}")

if len(df_2026) > 0:
    dates_2026 = df_2026['date_str'].unique().sort()
    print(f"2026年日期范围: {dates_2026[0]} ~ {dates_2026[-1]}")
    print(f"2026年交易日数: {len(dates_2026)}")
    
    # 检查股票数
    stocks_2026 = df_2026['stock_code'].unique()
    print(f"2026年股票数: {len(stocks_2026)}")
    
    # 检查某只股票的数据
    sample_stock = stocks_2026[0]
    sample_df = df_2026.filter(pl.col('stock_code') == sample_stock)
    print(f"\n示例股票 {sample_stock} 数据:")
    print(sample_df['date_str', 'close'].head(10))
