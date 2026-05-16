"""
对比：全部数据 vs 180天数据的 MACD 计算
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import pandas as pd
import numpy as np
import lancedb
from datetime import date
from numba import njit

@njit
def calc_ema_numba(arr, period):
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
    return ema

def calc_macd_numba(close, fast=12, slow=26, signal=9):
    ema_fast = calc_ema_numba(close, fast)
    ema_slow = calc_ema_numba(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema_numba(dif, signal)
    histogram = (dif - dea) * 2
    return histogram

# 连接 LanceDB
db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
table = db.open_table("daily_ohlcv")
daily_df = pl.from_arrow(table.to_arrow())

# 查找 688244
stock_688244 = daily_df.filter(pl.col('stock_code') == '688244')
stock_688244 = stock_688244.filter(pl.col('trade_date') <= date(2026, 1, 5))
stock_688244 = stock_688244.sort('trade_date')

close_all = stock_688244['close'].to_numpy()
print(f"LanceDB 总数据量: {len(close_all)} 天")

# 对比不同数据长度
for days in [60, 120, 180, len(close_all)]:
    if days > len(close_all):
        days = len(close_all)
    close_subset = close_all[-days:]
    macd = calc_macd_numba(close_subset)
    print(f"\n=== 最后 {days} 天数据 ===")
    print(f"MACD最后4根: {macd[-4:]}")
    print(f"最后一根MACD: {macd[-1]:.6f} ({'红柱' if macd[-1] > 0 else '绿柱'})")

print(f"\n=== 聚宽结果 ===")
print(f"聚宽 MACD最后4根: [-0.1155, -0.1038, -0.0544, -0.0015]")
print(f"最后一根MACD: -0.0015 (绿柱)")

print(f"\n=== 结论 ===")
print("本地策略用全部数据计算，聚宽用有限天数计算，结果必然不同！")
print("要复刻本地策略，聚宽需要获取足够长的历史数据（至少200+天）")
