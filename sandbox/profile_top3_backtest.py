"""
top3_backtest.py 性能分析

分析各环节耗时
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import lancedb
import polars as pl
import numpy as np
from datetime import datetime, timedelta


def profile_load_data():
    """分析 load_data 各环节耗时"""
    print("=" * 60)
    print("load_data 性能分析")
    print("=" * 60)
    
    start_date = "2026-01-01"
    end_date = "2026-03-13"
    
    # 1. 连接数据库
    t0 = time.perf_counter()
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    print(f"[1] 连接数据库: {(time.perf_counter() - t0)*1000:.1f}ms")
    
    # 2. 加载 stock_info
    t0 = time.perf_counter()
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    print(f"[2] 加载 stock_info: {(time.perf_counter() - t0)*1000:.1f}ms, {len(st_info_df)} 行")
    
    # 3. 过滤 ST 和新股
    t0 = time.perf_counter()
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    print(f"[3] 过滤 ST/新股: {(time.perf_counter() - t0)*1000:.1f}ms, ST={len(st_stocks)}, 新股={len(new_stocks)}")
    
    # 4. 加载日线数据（全量）
    t0 = time.perf_counter()
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    load_time = time.perf_counter() - t0
    print(f"[4] 加载 daily_ohlcv: {load_time*1000:.1f}ms, {len(daily_df)} 行, {len(daily_df.columns)} 列")
    print(f"    内存: {daily_df.estimated_size() / (1024*1024):.1f} MB")
    
    # 5. 逐行迭代构建字典（原代码方式）
    t0 = time.perf_counter()
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        sc = row['stock_code']
        if sc in st_stocks or sc in new_stocks:
            continue
        if sc not in daily_data:
            daily_data[sc] = {'dates': [], 'close': [], 'open': [], 'high': [], 'low': [], 'volume': []}
        daily_data[sc]['dates'].append(str(row['trade_date']))
        daily_data[sc]['close'].append(row['close'])
        daily_data[sc]['open'].append(row.get('open', row['close']))
        daily_data[sc]['high'].append(row.get('high', row['close']))
        daily_data[sc]['low'].append(row.get('low', row['close']))
        daily_data[sc]['volume'].append(row['volume'])
    iter_time = time.perf_counter() - t0
    print(f"[5] 逐行迭代构建字典: {iter_time*1000:.1f}ms, {len(daily_data)} 只股票")
    
    # 6. 排序和类型转换
    t0 = time.perf_counter()
    for sc in daily_data:
        idx = np.argsort(np.array(daily_data[sc]['dates']))
        for k in daily_data[sc]:
            arr = np.array(daily_data[sc][k])[idx]
            daily_data[sc][k] = arr.astype(np.float64) if k != 'dates' else arr
    sort_time = time.perf_counter() - t0
    print(f"[6] 排序和类型转换: {sort_time*1000:.1f}ms")
    
    print()
    print("=" * 60)
    print("耗时占比")
    print("=" * 60)
    total = load_time + iter_time + sort_time
    print(f"  加载数据: {load_time*1000:.1f}ms ({load_time/total*100:.1f}%)")
    print(f"  逐行迭代: {iter_time*1000:.1f}ms ({iter_time/total*100:.1f}%) ⚠️ 主要瓶颈")
    print(f"  排序转换: {sort_time*1000:.1f}ms ({sort_time/total*100:.1f}%)")
    
    return daily_data


def profile_backtest(daily_data):
    """分析回测环节耗时"""
    print()
    print("=" * 60)
    print("run_backtest 性能分析")
    print("=" * 60)
    
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
    def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(close)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        atr = np.zeros(n)
        atr[0] = tr[0]
        for i in range(1, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        return atr

    @njit
    def calc_std(close: np.ndarray, period: int) -> np.ndarray:
        n = len(close)
        result = np.zeros(n)
        for i in range(n):
            start = max(0, i - period + 1)
            result[i] = np.std(close[start:i+1])
        return result

    @njit
    def calc_vol_ma(volume: np.ndarray, period: int = 5) -> np.ndarray:
        n = len(volume)
        result = np.zeros(n)
        for i in range(n):
            start = max(0, i - period + 1)
            result[i] = np.mean(volume[start:i+1])
        return result

    @njit
    def detect_signal(bars: np.ndarray) -> np.ndarray:
        n = len(bars)
        signals = np.zeros(n, dtype=np.bool_)
        for i in range(3, n):
            b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
            if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
                if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                    signals[i] = True
        return signals

    @njit
    def calc_volatility_strength(close: np.ndarray, high: np.ndarray, low: np.ndarray, idx: int) -> float:
        if idx < 20 or idx >= len(close):
            return 0.0
        atr = calc_atr(high, low, close)
        std20 = calc_std(close, 20)
        atr_pct = atr[idx] / close[idx] * 100 if close[idx] > 0 else 0
        high_low_range = (high[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
        std20_pct = std20[idx] / close[idx] * 100 if close[idx] > 0 else 0
        lower_shadow = (close[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
        return 0.35 * (atr_pct - 3.0) / 1.5 + 0.30 * (high_low_range - 2.5) / 1.5 + 0.20 * (std20_pct - 3.5) / 1.5 + 0.15 * (lower_shadow - 1.5) / 1.5

    start_date = "2026-01-01"
    end_date = "2026-03-13"
    
    # 逐股票计算指标
    t0 = time.perf_counter()
    all_trades = []
    
    stock_count = 0
    for sc in sorted(daily_data.keys()):
        d = daily_data[sc]
        dates, close = d['dates'], d['close']
        open_prices = d['open']
        high, low, volume = d['high'], d['low'], d['volume']
        
        if len(close) < 50:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        hist = calc_macd(close)
        rsi = calc_rsi(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if not signals[i]:
                continue
            
            if dates[i] < start_date or dates[i] > end_date:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close):
                continue
            
            vs = calc_volatility_strength(close, high, low, i)
            
            buy_price = open_prices[buy_idx]
            peak_price = buy_price
            triggered = False
            sell_price = buy_price
            hold_days = 0
            
            for day in range(10):
                chk = buy_idx + day
                if chk >= len(close):
                    sell_price = close[-1]
                    hold_days = day
                    break
                if high[chk] > peak_price:
                    peak_price = high[chk]
                if (high[chk] - buy_price) / buy_price >= 0.03:
                    triggered = True
                if triggered and (peak_price - close[chk]) / peak_price >= 0.02:
                    sell_price = close[chk]
                    hold_days = day + 1
                    break
                sell_price = close[chk]
                hold_days = day + 1
            
            ret = (sell_price - buy_price) / buy_price
            sell_date = str(dates[min(buy_idx + hold_days, len(dates) - 1)])
            
            all_trades.append({
                'stock_code': sc,
                'buy_date': str(dates[buy_idx]),
                'sell_date': sell_date,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'return': ret,
                'vs': vs,
            })
        
        stock_count += 1
    
    backtest_time = time.perf_counter() - t0
    print(f"逐股票回测: {backtest_time*1000:.1f}ms, {stock_count} 只股票, {len(all_trades)} 笔交易")
    
    return all_trades


if __name__ == "__main__":
    daily_data = profile_load_data()
    trades = profile_backtest(daily_data)
