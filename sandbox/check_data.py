"""
检查 LanceDB 数据的 open/close 是否正确
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import lancedb
from datetime import date

# 连接 LanceDB
db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
table = db.open_table("daily_ohlcv")
daily_df = pl.from_arrow(table.to_arrow())

# 查找 688244 最近几天的数据
stock = daily_df.filter(pl.col('stock_code') == '688244')
stock = stock.filter(pl.col('trade_date') >= date(2026, 1, 1))
stock = stock.sort('trade_date')

print("=== 688244 最近数据 ===")
print(stock[['trade_date', 'open', 'high', 'low', 'close']])

print("\n=== 检查 open 和 close 的关系 ===")
# 正常情况下：high >= max(open, close), low <= min(open, close)
# 如果 open 和 close 搞反了，这个关系可能不对

for row in stock.iter_rows(named=True):
    o, h, l, c = row['open'], row['high'], row['low'], row['close']
    d = row['trade_date']
    
    # 检查 high >= max(open, close)
    check1 = h >= max(o, c)
    # 检查 low <= min(open, close)
    check2 = l <= min(o, c)
    
    status = "OK" if (check1 and check2) else "ERROR"
    print(f"{d}: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f} -> {status}")
    
    if not (check1 and check2):
        print(f"  high({h:.2f}) should >= max(open, close)={max(o,c):.2f}: {check1}")
        print(f"  low({l:.2f}) should <= min(open, close)={min(o,c):.2f}: {check2}")
