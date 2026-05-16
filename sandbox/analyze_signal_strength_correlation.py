"""
分析信号日特征与第1天强势的相关性

核心问题：我们无法在买入时预判哪些会强势，只能等第1天收盘才知道

研究目标：找出信号日哪些特征能预测第1天的强势程度
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict, List

from config.logger import get_logger

logger = get_logger(__name__)


def calculate_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    n = len(close)
    histogram = np.empty(n, dtype=np.float64)
    
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    alpha_signal = 2.0 / (signal + 1)
    
    ema_fast = close[0]
    ema_slow = close[0]
    dea = 0.0
    
    for i in range(n):
        ema_fast = alpha_fast * close[i] + (1 - alpha_fast) * ema_fast
        ema_slow = alpha_slow * close[i] + (1 - alpha_slow) * ema_slow
        dif = ema_fast - ema_slow
        dea = alpha_signal * dif + (1 - alpha_signal) * dea
        histogram[i] = (dif - dea) * 2
    
    return histogram


def calculate_volume_ma(volume: np.ndarray, period: int = 5):
    n = len(volume)
    result = np.empty(n, dtype=np.float64)
    
    cumsum = 0.0
    for i in range(n):
        cumsum += volume[i]
        if i >= period:
            cumsum -= volume[i - period]
        result[i] = cumsum / min(i + 1, period)
    
    return result


def calculate_rsi(close: np.ndarray, period: int = 14):
    n = len(close)
    rsi = np.empty(n, dtype=np.float64)
    rsi[:period] = 50.0
    
    gains = np.zeros(n)
    losses = np.zeros(n)
    
    for i in range(1, n):
        change = close[i] - close[i-1]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = abs(change)
    
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    for i in range(period, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14):
    n = len(close)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    atr = np.empty(n, dtype=np.float64)
    atr[:period] = np.mean(tr[:period])
    
    for i in range(period, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr


def calculate_stock_rank(daily_data: dict, trade_date: str, industry_stocks: list) -> Dict[str, float]:
    stocks_in_industry = []
    
    for stock_code in industry_stocks:
        stock_data = daily_data.get(stock_code)
        if not stock_data:
            continue
        
        dates = stock_data['dates']
        close = stock_data['close']
        
        idx = np.where(dates == trade_date)[0]
        if len(idx) == 0:
            continue
        idx = idx[0]
        if idx < 1:
            continue
        
        pct_chg = (close[idx] - close[idx-1]) / close[idx-1] * 100
        stocks_in_industry.append((stock_code, pct_chg))
    
    if not stocks_in_industry:
        return {}
    
    stocks_in_industry.sort(key=lambda x: x[1], reverse=True)
    
    n = len(stocks_in_industry)
    rank_dict = {}
    for i, (stock_code, pct_chg) in enumerate(stocks_in_industry):
        rank_percentile = (n - i) / n * 100
        rank_dict[stock_code] = rank_percentile
    
    return rank_dict


def load_data(start_date: str, end_date: str):
    print("\n" + "="*60)
    print(f"加载数据: {start_date} - {end_date}")
    print("="*60)
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print("\n[1/3] 加载股票信息...")
    table = db.open_table("stock_info")
    stock_info_df = pl.from_arrow(table.to_arrow())
    
    stock_info = {}
    industry_stocks = {}
    for row in stock_info_df.iter_rows(named=True):
        stock_info[row['stock_code']] = {
            'name': row.get('stock_name', ''),
            'industry': row.get('industry'),
        }
        industry = row.get('industry')
        if industry:
            if industry not in industry_stocks:
                industry_stocks[industry] = []
            industry_stocks[industry].append(row['stock_code'])
    
    print(f"  股票信息: {len(stock_info)} 只")
    
    print("\n[2/3] 加载日线数据...")
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_df = daily_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        stock_code = row['stock_code']
        if stock_code not in daily_data:
            daily_data[stock_code] = {
                'dates': [],
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
            }
        daily_data[stock_code]['dates'].append(str(row['trade_date']))
        daily_data[stock_code]['open'].append(row.get('open', row.get('close')))
        daily_data[stock_code]['high'].append(row.get('high', row.get('close')))
        daily_data[stock_code]['low'].append(row.get('low', row.get('close')))
        daily_data[stock_code]['close'].append(row['close'])
        daily_data[stock_code]['volume'].append(row['volume'])
    
    for stock_code in daily_data:
        dates_arr = np.array(daily_data[stock_code]['dates'])
        sorted_idx = np.argsort(dates_arr)
        
        for key in ['dates', 'open', 'high', 'low', 'close', 'volume']:
            arr = np.array(daily_data[stock_code][key])
            daily_data[stock_code][key] = arr[sorted_idx]
    
    print(f"  日线数据: {len(daily_data)} 只股票")
    
    return stock_info, daily_data, industry_stocks


def analyze_signal_features(daily_data, stock_info, industry_stocks):
    """
    分析信号日特征与第1天强势的相关性
    """
    signals = []
    date_industry_ranks = {}
    
    for stock_code in daily_data:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
        low = stock_data['low']
        open_price = stock_data['open']
        volume = stock_data['volume']
        dates = stock_data['dates']
        
        if len(close) < 50:
            continue
        
        info = stock_info.get(stock_code, {})
        industry = info.get('industry')
        if not industry:
            continue
        
        histogram = calculate_macd(close)
        volume_ma5 = calculate_volume_ma(volume)
        rsi = calculate_rsi(close)
        atr = calculate_atr(high, low, close)
        
        for i in range(4, len(histogram) - 25):
            bars = histogram[i-3:i+1]
            
            if not np.all(bars < 0):
                continue
            if not (bars[0] < bars[1] < bars[2] < bars[3]):
                continue
            
            diff1 = bars[1] - bars[0]
            diff2 = bars[2] - bars[1]
            diff3 = bars[3] - bars[2]
            if not (diff1 < diff2 and diff2 < diff3):
                continue
            
            if bars[3] > -0.005:
                continue
            
            vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
            if vol_ratio < 1.5:
                continue
            
            trade_date = dates[i]
            
            cache_key = (trade_date, industry)
            if cache_key not in date_industry_ranks:
                industry_stock_list = industry_stocks.get(industry, [])
                date_industry_ranks[cache_key] = calculate_stock_rank(
                    daily_data, trade_date, industry_stock_list
                )
            
            rank_dict = date_industry_ranks[cache_key]
            stock_rank = rank_dict.get(stock_code, 0)
            
            if stock_rank < 80:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - 20:
                continue
            
            buy_price = close[buy_idx]
            buy_open = open_price[buy_idx]
            
            day1_open = open_price[buy_idx + 1] if buy_idx + 1 < len(open_price) else buy_price
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_low = low[buy_idx + 1] if buy_idx + 1 < len(low) else buy_price
            day1_close = close[buy_idx + 1] if buy_idx + 1 < len(close) else buy_price
            
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            day1_close_ret = (day1_close - buy_price) / buy_price * 100
            day1_open_ret = (day1_open - buy_price) / buy_price * 100
            day1_range = (day1_high - day1_low) / buy_price * 100
            
            signal_features = {
                'stock_code': stock_code,
                'trade_date': trade_date,
                'day1_high_ret': day1_high_ret,
                'day1_close_ret': day1_close_ret,
                'is_strong': day1_high_ret >= 3,
                
                'histogram_value': bars[3],
                'histogram_accel': diff3 - diff2,
                'vol_ratio': vol_ratio,
                'stock_rank': stock_rank,
                'rsi': rsi[i],
                'atr_pct': atr[i] / close[i] * 100 if atr[i] > 0 else 0,
                
                'signal_day_pct': (close[i] - close[i-1]) / close[i-1] * 100,
                'signal_day_range': (high[i] - low[i]) / close[i-1] * 100,
                'signal_day_upper_shadow': (high[i] - close[i]) / close[i-1] * 100,
                'signal_day_lower_shadow': (low[i] - close[i]) / close[i-1] * 100,
                
                'buy_gap': (buy_open - close[i]) / close[i] * 100,
                
                'prev_5d_ret': (close[i] - close[max(0, i-5)]) / close[max(0, i-5)] * 100,
                'prev_10d_ret': (close[i] - close[max(0, i-10)]) / close[max(0, i-10)] * 100,
                'prev_20d_ret': (close[i] - close[max(0, i-20)]) / close[max(0, i-20)] * 100,
                
                'day1_open_ret': day1_open_ret,
                'day1_range': day1_range,
            }
            
            signals.append(signal_features)
    
    return signals


def main():
    print("\n" + "="*70)
    print("信号日特征与第1天强势的相关性分析")
    print("="*70)
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    signals = analyze_signal_features(daily_data, stock_info, industry_stocks)
    
    print(f"\n总信号数: {len(signals)}")
    
    strong_signals = [s for s in signals if s['is_strong']]
    weak_signals = [s for s in signals if not s['is_strong']]
    
    print(f"强势信号(第1天>=3%): {len(strong_signals)} ({len(strong_signals)/len(signals)*100:.1f}%)")
    print(f"弱势信号(第1天<3%): {len(weak_signals)} ({len(weak_signals)/len(signals)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("【特征对比：强势 vs 弱势】")
    print("="*70)
    
    features = [
        ('histogram_value', 'MACD绿柱值'),
        ('histogram_accel', '绿柱收缩加速度'),
        ('vol_ratio', '成交量比'),
        ('stock_rank', '板块排名'),
        ('rsi', 'RSI'),
        ('atr_pct', 'ATR%'),
        ('signal_day_pct', '信号日涨幅%'),
        ('signal_day_range', '信号日振幅%'),
        ('signal_day_upper_shadow', '信号日上影线%'),
        ('signal_day_lower_shadow', '信号日下影线%'),
        ('buy_gap', '买入日跳空%'),
        ('prev_5d_ret', '前5日涨幅%'),
        ('prev_10d_ret', '前10日涨幅%'),
        ('prev_20d_ret', '前20日涨幅%'),
        ('day1_open_ret', '第1天开盘涨幅%'),
        ('day1_range', '第1天振幅%'),
    ]
    
    print(f"\n{'特征':>20} {'强势均值':>12} {'弱势均值':>12} {'差异':>10} {'区分度':>8}")
    print("-"*70)
    
    for feature_key, feature_name in features:
        strong_vals = [s[feature_key] for s in strong_signals]
        weak_vals = [s[feature_key] for s in weak_signals]
        
        strong_mean = np.mean(strong_vals)
        weak_mean = np.mean(weak_vals)
        diff = strong_mean - weak_mean
        
        all_vals = [s[feature_key] for s in signals]
        all_std = np.std(all_vals)
        discriminative = abs(diff) / all_std if all_std > 0 else 0
        
        print(f"{feature_name:>20} {strong_mean:>+12.3f} {weak_mean:>+12.3f} {diff:>+10.3f} {discriminative:>8.2f}")
    
    print("\n" + "="*70)
    print("【按特征分组的强势概率】")
    print("="*70)
    
    def analyze_feature_bins(signals, feature_key, bins):
        all_vals = [s[feature_key] for s in signals]
        min_val, max_val = min(all_vals), max(all_vals)
        
        if min_val == max_val:
            return
        
        bin_edges = np.linspace(min_val, max_val, bins + 1)
        
        print(f"\n{feature_key}:")
        print(f"{'区间':>20} {'信号数':>8} {'强势数':>8} {'强势概率':>10}")
        print("-"*50)
        
        for i in range(bins):
            low, high = bin_edges[i], bin_edges[i+1]
            bin_signals = [s for s in signals if low <= s[feature_key] < high]
            if not bin_signals:
                continue
            
            strong_count = sum(1 for s in bin_signals if s['is_strong'])
            prob = strong_count / len(bin_signals) * 100
            
            print(f"[{low:>+8.3f}, {high:>+8.3f}] {len(bin_signals):>8} {strong_count:>8} {prob:>9.1f}%")
    
    analyze_feature_bins(signals, 'vol_ratio', 5)
    analyze_feature_bins(signals, 'stock_rank', 5)
    analyze_feature_bins(signals, 'signal_day_pct', 5)
    analyze_feature_bins(signals, 'buy_gap', 5)
    analyze_feature_bins(signals, 'day1_open_ret', 5)
    analyze_feature_bins(signals, 'day1_range', 5)
    
    print("\n" + "="*70)
    print("【第1天开盘涨幅与强势的关系】")
    print("="*70)
    
    open_ret_bins = [(-10, -2), (-2, -1), (-1, 0), (0, 0.5), (0.5, 1), (1, 2), (2, 3), (3, 5), (5, 10)]
    
    print(f"\n{'开盘涨幅区间':>15} {'信号数':>8} {'强势数':>8} {'强势概率':>10} {'平均第1天最高':>12}")
    print("-"*60)
    
    for low, high in open_ret_bins:
        bin_signals = [s for s in signals if low <= s['day1_open_ret'] < high]
        if not bin_signals:
            continue
        
        strong_count = sum(1 for s in bin_signals if s['is_strong'])
        prob = strong_count / len(bin_signals) * 100
        avg_high_ret = np.mean([s['day1_high_ret'] for s in bin_signals])
        
        print(f"[{low:>+5.1f}%, {high:>+5.1f}%] {len(bin_signals):>8} {strong_count:>8} {prob:>9.1f}% {avg_high_ret:>+11.2f}%")


if __name__ == "__main__":
    main()
