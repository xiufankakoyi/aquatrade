"""
重新分析策略时间线

原策略：
- T日收盘确认信号
- T+1日收盘买入
- "第1天" = T+2日

问题：T+2日的强势在T+1日买入时无法预判

本脚本分析：T+1日（买入日）的特征能否预测T+2日的强势
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict

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


def analyze_timeline(daily_data, stock_info, industry_stocks):
    """
    分析时间线和特征预测能力
    
    时间线：
    - T日：信号日（MACD绿柱收缩）
    - T+1日：买入日（收盘买入）
    - T+2日：第1天（观察是否强势）
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
            
            t0_idx = i
            t1_idx = i + 1
            t2_idx = i + 2
            
            if t2_idx >= len(close) - 20:
                continue
            
            t0_close = close[t0_idx]
            t1_open = open_price[t1_idx]
            t1_close = close[t1_idx]
            t1_high = high[t1_idx]
            t1_low = low[t1_idx]
            t1_volume = volume[t1_idx]
            
            t2_open = open_price[t2_idx]
            t2_close = close[t2_idx]
            t2_high = high[t2_idx]
            t2_low = low[t2_idx]
            
            buy_price = t1_close
            day1_high_ret = (t2_high - buy_price) / buy_price * 100
            day1_close_ret = (t2_close - buy_price) / buy_price * 100
            
            signal = {
                'stock_code': stock_code,
                't0_date': dates[t0_idx],
                't1_date': dates[t1_idx],
                't2_date': dates[t2_idx],
                
                'is_strong': day1_high_ret >= 3,
                'day1_high_ret': day1_high_ret,
                'day1_close_ret': day1_close_ret,
                
                't0_features': {
                    'histogram_value': bars[3],
                    'vol_ratio': vol_ratio,
                    'stock_rank': stock_rank,
                    't0_pct': (t0_close - close[t0_idx-1]) / close[t0_idx-1] * 100,
                },
                
                't1_features': {
                    't1_open_ret': (t1_open - t0_close) / t0_close * 100,
                    't1_close_ret': (t1_close - t0_close) / t0_close * 100,
                    't1_high_ret': (t1_high - t0_close) / t0_close * 100,
                    't1_low_ret': (t1_low - t0_close) / t0_close * 100,
                    't1_range': (t1_high - t1_low) / t0_close * 100,
                    't1_vol_ratio': t1_volume / volume_ma5[t1_idx] if volume_ma5[t1_idx] > 0 else 0,
                },
                
                't2_features': {
                    't2_open_ret': (t2_open - buy_price) / buy_price * 100,
                },
            }
            
            signals.append(signal)
    
    return signals


def main():
    print("\n" + "="*70)
    print("重新分析策略时间线")
    print("="*70)
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    signals = analyze_timeline(daily_data, stock_info, industry_stocks)
    
    print(f"\n总信号数: {len(signals)}")
    
    strong_signals = [s for s in signals if s['is_strong']]
    weak_signals = [s for s in signals if not s['is_strong']]
    
    print(f"强势信号(T+2日最高>=3%): {len(strong_signals)} ({len(strong_signals)/len(signals)*100:.1f}%)")
    print(f"弱势信号(T+2日最高<3%): {len(weak_signals)} ({len(weak_signals)/len(signals)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("【T+1日特征 vs T+2日强势】")
    print("="*70)
    
    t1_features = [
        ('t1_open_ret', 'T+1开盘涨幅%'),
        ('t1_close_ret', 'T+1收盘涨幅%'),
        ('t1_high_ret', 'T+1最高涨幅%'),
        ('t1_low_ret', 'T+1最低涨幅%'),
        ('t1_range', 'T+1振幅%'),
        ('t1_vol_ratio', 'T+1量比'),
    ]
    
    print(f"\n{'特征':>20} {'强势均值':>12} {'弱势均值':>12} {'差异':>10} {'区分度':>8}")
    print("-"*70)
    
    for feature_key, feature_name in t1_features:
        strong_vals = [s['t1_features'][feature_key] for s in strong_signals]
        weak_vals = [s['t1_features'][feature_key] for s in weak_signals]
        
        strong_mean = np.mean(strong_vals)
        weak_mean = np.mean(weak_vals)
        diff = strong_mean - weak_mean
        
        all_vals = [s['t1_features'][feature_key] for s in signals]
        all_std = np.std(all_vals)
        discriminative = abs(diff) / all_std if all_std > 0 else 0
        
        print(f"{feature_name:>20} {strong_mean:>+12.3f} {weak_mean:>+12.3f} {diff:>+10.3f} {discriminative:>8.2f}")
    
    print("\n" + "="*70)
    print("【T+1日收盘涨幅 vs T+2日强势】")
    print("="*70)
    
    close_ret_bins = [(-10, -3), (-3, -1), (-1, 0), (0, 1), (1, 2), (2, 3), (3, 5), (5, 10)]
    
    print(f"\n{'T+1收盘涨幅':>15} {'信号数':>8} {'强势数':>8} {'强势概率':>10} {'T+2平均最高':>12}")
    print("-"*60)
    
    for low, high in close_ret_bins:
        bin_signals = [s for s in signals if low <= s['t1_features']['t1_close_ret'] < high]
        if not bin_signals:
            continue
        
        strong_count = sum(1 for s in bin_signals if s['is_strong'])
        prob = strong_count / len(bin_signals) * 100
        avg_t2_high = np.mean([s['day1_high_ret'] for s in bin_signals])
        
        print(f"[{low:>+5.0f}%, {high:>+5.0f}%] {len(bin_signals):>8} {strong_count:>8} {prob:>9.1f}% {avg_t2_high:>+11.2f}%")
    
    print("\n" + "="*70)
    print("【关键洞察】")
    print("="*70)
    print("""
时间线分析：
- T日：信号日（MACD绿柱收缩）
- T+1日：买入日（收盘买入）
- T+2日：第1天（观察是否强势）

问题：T+1日收盘买入时，T+2日的强势未知

可能的解决方案：
1. 改为T+1日开盘买入，观察T+1日盘中走势
2. 改为T+2日开盘确认后再买入
3. 用T+1日的特征预测T+2日的强势
""")


if __name__ == "__main__":
    main()
