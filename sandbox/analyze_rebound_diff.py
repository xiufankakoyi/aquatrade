"""
分析小反弹、中反弹、大反弹的区别

目标：找出买入时或买入后早期的特征，用于判断反弹类型
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
from typing import Dict

from sandbox.data_cache import get_cache, calculate_macd_numba, calculate_volume_ma_numba


def calculate_stock_rank_on_date(data, trade_date: str, industry: str) -> Dict[str, float]:
    stocks_in_industry = []
    
    for stock_code, stock_info in data.stock_info.items():
        if stock_info.get('industry') != industry:
            continue
        
        stock_data = data.daily_data.get(stock_code)
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


def analyze_rebound_differences():
    print("\n" + "="*70)
    print("小反弹 vs 中反弹 vs 大反弹 特征分析")
    print("="*70)
    
    data = get_cache()
    date_industry_ranks = {}
    
    trades = []
    
    for stock_code in data.stock_codes:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
        low = stock_data['low']
        volume = stock_data['volume']
        dates = stock_data['dates']
        
        if len(close) < 50:
            continue
        
        info = data.stock_info.get(stock_code, {})
        industry = info.get('industry')
        if not industry:
            continue
        
        dif, dea, histogram = calculate_macd_numba(close)
        volume_ma5 = calculate_volume_ma_numba(volume)
        
        for i in range(4, len(histogram) - 30):
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
            
            if bars[3] <= -0.01:
                continue
            
            vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
            if vol_ratio < 1.5:
                continue
            
            trade_date = dates[i]
            
            cache_key = (trade_date, industry)
            if cache_key not in date_industry_ranks:
                date_industry_ranks[cache_key] = calculate_stock_rank_on_date(data, trade_date, industry)
            
            rank_dict = date_industry_ranks[cache_key]
            stock_rank = rank_dict.get(stock_code, 0)
            
            if stock_rank < 80:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - 20:
                continue
            
            buy_price = close[buy_idx]
            
            max_profit_3d = 0
            for d in range(1, 4):
                if buy_idx + d >= len(high):
                    break
                profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                if profit > max_profit_3d:
                    max_profit_3d = profit
            
            if max_profit_3d <= 3:
                rebound_type = 'small'
            elif max_profit_3d <= 8:
                rebound_type = 'medium'
            else:
                rebound_type = 'large'
            
            prev_close_5d = close[buy_idx-5] if buy_idx >= 5 else close[0]
            prev_close_10d = close[buy_idx-10] if buy_idx >= 10 else close[0]
            prev_low_20d = np.min(low[buy_idx-20:buy_idx]) if buy_idx >= 20 else np.min(low[:buy_idx])
            
            ret_5d_before = (buy_price - prev_close_5d) / prev_close_5d * 100
            ret_10d_before = (buy_price - prev_close_10d) / prev_close_10d * 100
            dist_from_low_20d = (buy_price - prev_low_20d) / prev_low_20d * 100
            
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_close = close[buy_idx + 1] if buy_idx + 1 < len(close) else buy_price
            day1_ret = (day1_close - buy_price) / buy_price * 100
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            day2_high = high[buy_idx + 2] if buy_idx + 2 < len(high) else buy_price
            day2_close = close[buy_idx + 2] if buy_idx + 2 < len(close) else buy_price
            day2_ret = (day2_close - buy_price) / buy_price * 100
            day2_high_ret = (day2_high - buy_price) / buy_price * 100
            
            trades.append({
                'rebound_type': rebound_type,
                'max_profit_3d': max_profit_3d,
                'histogram': bars[3],
                'histogram_diff': diff3,
                'vol_ratio': vol_ratio,
                'stock_rank': stock_rank,
                'ret_5d_before': ret_5d_before,
                'ret_10d_before': ret_10d_before,
                'dist_from_low_20d': dist_from_low_20d,
                'day1_ret': day1_ret,
                'day1_high_ret': day1_high_ret,
                'day2_ret': day2_ret,
                'day2_high_ret': day2_high_ret,
            })
    
    print(f"\n共 {len(trades)} 笔交易")
    
    small = [t for t in trades if t['rebound_type'] == 'small']
    medium = [t for t in trades if t['rebound_type'] == 'medium']
    large = [t for t in trades if t['rebound_type'] == 'large']
    
    print("\n" + "="*70)
    print("【买入时的特征对比】")
    print("="*70)
    
    features = [
        ('histogram', 'MACD绿柱值'),
        ('histogram_diff', '绿柱收缩速度'),
        ('vol_ratio', '成交量比'),
        ('stock_rank', '板块排名'),
        ('ret_5d_before', '前5天跌幅'),
        ('ret_10d_before', '前10天跌幅'),
        ('dist_from_low_20d', '距20日低点'),
    ]
    
    print(f"\n{'特征':>15} {'小反弹':>12} {'中反弹':>12} {'大反弹':>12}")
    print("-"*55)
    
    for key, name in features:
        small_val = np.mean([t[key] for t in small])
        medium_val = np.mean([t[key] for t in medium])
        large_val = np.mean([t[key] for t in large])
        
        print(f"{name:>15} {small_val:>12.3f} {medium_val:>12.3f} {large_val:>12.3f}")
    
    print("\n" + "="*70)
    print("【买入后第1天、第2天的特征对比】")
    print("="*70)
    
    day_features = [
        ('day1_ret', '第1天收盘收益%'),
        ('day1_high_ret', '第1天最高收益%'),
        ('day2_ret', '第2天收盘收益%'),
        ('day2_high_ret', '第2天最高收益%'),
    ]
    
    print(f"\n{'特征':>15} {'小反弹':>12} {'中反弹':>12} {'大反弹':>12}")
    print("-"*55)
    
    for key, name in day_features:
        small_val = np.mean([t[key] for t in small])
        medium_val = np.mean([t[key] for t in medium])
        large_val = np.mean([t[key] for t in large])
        
        print(f"{name:>15} {small_val:>12.2f} {medium_val:>12.2f} {large_val:>12.2f}")
    
    print("\n" + "="*70)
    print("【第1天涨幅分布】")
    print("="*70)
    
    print(f"\n{'第1天涨幅':>12} {'小反弹':>10} {'中反弹':>10} {'大反弹':>10}")
    print("-"*45)
    
    for threshold in [0, 1, 2, 3]:
        small_pct = np.sum([1 for t in small if t['day1_high_ret'] > threshold]) / len(small) * 100
        medium_pct = np.sum([1 for t in medium if t['day1_high_ret'] > threshold]) / len(medium) * 100
        large_pct = np.sum([1 for t in large if t['day1_high_ret'] > threshold]) / len(large) * 100
        
        print(f">{threshold}%: {small_pct:>10.1f}% {medium_pct:>10.1f}% {large_pct:>10.1f}%")
    
    print("\n" + "="*70)
    print("【第2天涨幅分布】")
    print("="*70)
    
    print(f"\n{'第2天涨幅':>12} {'小反弹':>10} {'中反弹':>10} {'大反弹':>10}")
    print("-"*45)
    
    for threshold in [0, 1, 2, 3, 5]:
        small_pct = np.sum([1 for t in small if t['day2_high_ret'] > threshold]) / len(small) * 100
        medium_pct = np.sum([1 for t in medium if t['day2_high_ret'] > threshold]) / len(medium) * 100
        large_pct = np.sum([1 for t in large if t['day2_high_ret'] > threshold]) / len(large) * 100
        
        print(f">{threshold}%: {small_pct:>10.1f}% {medium_pct:>10.1f}% {large_pct:>10.1f}%")
    
    print("\n" + "="*70)
    print("【关键发现】")
    print("="*70)
    
    small_day1_gt1 = np.sum([1 for t in small if t['day1_high_ret'] > 1]) / len(small) * 100
    medium_day1_gt1 = np.sum([1 for t in medium if t['day1_high_ret'] > 1]) / len(medium) * 100
    large_day1_gt1 = np.sum([1 for t in large if t['day1_high_ret'] > 1]) / len(large) * 100
    
    small_day2_gt2 = np.sum([1 for t in small if t['day2_high_ret'] > 2]) / len(small) * 100
    medium_day2_gt2 = np.sum([1 for t in medium if t['day2_high_ret'] > 2]) / len(medium) * 100
    large_day2_gt2 = np.sum([1 for t in large if t['day2_high_ret'] > 2]) / len(large) * 100
    
    print(f"\n第1天最高涨幅>1%:")
    print(f"  小反弹: {small_day1_gt1:.1f}%")
    print(f"  中反弹: {medium_day1_gt1:.1f}%")
    print(f"  大反弹: {large_day1_gt1:.1f}%")
    
    print(f"\n第2天最高涨幅>2%:")
    print(f"  小反弹: {small_day2_gt2:.1f}%")
    print(f"  中反弹: {medium_day2_gt2:.1f}%")
    print(f"  大反弹: {large_day2_gt2:.1f}%")
    
    print("\n" + "="*70)
    print("【判断规则建议】")
    print("="*70)
    
    print("\n买入后第1天收盘判断:")
    print("  - 第1天最高涨幅 < 1% → 可能是小反弹")
    print("  - 第1天最高涨幅 >= 1% → 可能是中/大反弹")
    
    print("\n买入后第2天收盘判断:")
    print("  - 前2天最高涨幅 < 2% → 小反弹概率高，考虑卖出")
    print("  - 前2天最高涨幅 >= 2% → 中/大反弹概率高，继续持有")


if __name__ == "__main__":
    analyze_rebound_differences()
