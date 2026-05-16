"""
检查价格数据
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("检查价格数据")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

# 聚宽交易日期
jq_dates = [
    '2025-01-21', '2025-01-24',
    '2025-02-10', '2025-02-27',
    '2025-04-18', '2025-04-28',
    '2025-05-12', '2025-07-18',
    '2025-08-08', '2025-08-15',
    '2025-08-27', '2025-09-02',
    '2025-10-16', '2025-10-31',
    '2025-11-07', '2025-11-28',
    '2025-12-19', '2025-12-29'
]

# 聚宽交易价格
jq_prices = {
    '2025-01-21': 11.46,  # buy
    '2025-01-24': 11.31,  # sell
    '2025-02-10': 11.39,  # buy
    '2025-02-27': 11.52,  # sell
    '2025-04-18': 11.05,  # buy
    '2025-04-28': 10.99,  # sell
    '2025-05-12': 11.17,  # buy
    '2025-07-18': 12.60,  # sell
    '2025-08-08': 12.50,  # buy
    '2025-08-15': 12.21,  # sell
    '2025-08-27': 12.34,  # buy
    '2025-09-02': 11.84,  # sell
    '2025-10-16': 11.39,  # buy
    '2025-10-31': 11.37,  # sell
    '2025-11-07': 11.53,  # buy
    '2025-11-28': 11.66,  # sell
    '2025-12-19': 11.64,  # buy
    '2025-12-29': 11.53   # sell
}

# 读取数据
df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('stock_code') == '000001') &
    (pl.col('trade_date').is_in(jq_dates))
).select(['trade_date', 'open', 'close']).collect()

print(f"\n【价格对比】")
print(f"{'日期':<12} {'开盘价':<10} {'聚宽价格':<10} {'差异%':<10}")
print("-" * 42)

df_sorted = df.sort('trade_date')
for row in df_sorted.iter_rows():
    date, open_p, close_p = row
    jq_p = jq_prices.get(date, None)
    if jq_p:
        diff = (open_p - jq_p) / jq_p * 100
        print(f"{date:<12} {open_p:<10.2f} {jq_p:<10.2f} {diff:<10.2f}%")
