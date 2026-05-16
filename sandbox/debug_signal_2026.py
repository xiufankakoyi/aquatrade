"""
调试2026年信号检测
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
import polars as pl
import numpy as np
from numba import njit

@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
    return ema

@njit
def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return histogram

@njit
def calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    rsi = np.zeros(n)
    gains = np.zeros(n)
    losses = np.zeros(n)
    for i in range(1, n):
        change = close[i] - close[i-1]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = -change
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    for i in range(period, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    rsi[:period] = 50
    return rsi

@njit
def detect_green_bar_contraction(histogram: np.ndarray) -> np.ndarray:
    n = len(histogram)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = histogram[i-3], histogram[i-2], histogram[i-1], histogram[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                signals[i] = True
    return signals

db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
table = db.open_table("daily_ohlcv")
df = pl.from_arrow(table.to_arrow())

# 获取有2026年数据的股票
df_2026 = df.filter(pl.col('trade_date') >= pl.lit('2026-01-01').cast(pl.Date))
stocks_2026 = df_2026['stock_code'].unique()
print(f"有2026年数据的股票数: {len(stocks_2026)}")

# 选一只股票测试
test_stock = stocks_2026[0]
stock_df = df.filter(pl.col('stock_code') == test_stock).sort('trade_date')

print(f"\n股票 {test_stock} 数据:")
print(f"  总行数: {len(stock_df)}")

if len(stock_df) > 0:
    # 转换数据
    dates = np.array([str(d)[:10] for d in stock_df['trade_date']])
    close = stock_df['close'].to_numpy().astype(np.float64)
    
    print(f"  日期范围: {dates[0]} ~ {dates[-1]}")
    
    # 计算指标
    hist = calc_macd(close)
    rsi = calc_rsi(close)
    signals = detect_green_bar_contraction(hist)
    
    print(f"  总MACD信号数: {np.sum(signals)}")
    
    # 检查2026年的数据
    mask_2026 = (dates >= '2026-01-01') & (dates <= '2026-03-10')
    print(f"  2026年数据点数: {np.sum(mask_2026)}")
    
    if np.sum(mask_2026) > 0:
        idx_2026 = np.where(mask_2026)[0]
        print(f"  2026年索引范围: {idx_2026[0]} ~ {idx_2026[-1]}")
        
        # 检查这段时间的MACD
        for i in idx_2026:
            if i >= 3:
                b0, b1, b2, b3 = hist[i-3], hist[i-2], hist[i-1], hist[i]
                if signals[i]:
                    print(f"  {dates[i]}: MACD={hist[i]:.4f}, RSI={rsi[i]:.1f}, 信号=True ***")

# 统计所有股票的信号
print("\n统计所有股票2026年信号...")
all_signals = 0
for sc in stocks_2026[:500]:
    stock_df = df.filter(pl.col('stock_code') == sc).sort('trade_date')
    if len(stock_df) < 50:
        continue
    dates = np.array([str(d)[:10] for d in stock_df['trade_date']])
    close = stock_df['close'].to_numpy().astype(np.float64)
    if len(close) < 50:
        continue
    hist = calc_macd(close)
    signals = detect_green_bar_contraction(hist)
    mask_2026 = (dates >= '2026-01-01') & (dates <= '2026-03-10')
    if np.any(mask_2026):
        idx_2026 = np.where(mask_2026)[0]
        for i in idx_2026:
            if i < len(signals) and signals[i]:
                all_signals += 1

print(f"前500只股票2026年信号数: {all_signals}")
