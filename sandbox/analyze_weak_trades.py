"""
分析弱势交易的特征

目标：找出弱势交易在买入时的特征，用于预判或过滤
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


def analyze_weak_trades():
    print("\n" + "="*70)
    print("弱势交易特征分析")
    print("="*70)
    print("目标：找出弱势交易在买入时的特征，用于预判或过滤")
    
    data = get_cache()
    date_industry_ranks = {}
    
    weak_trades = []
    medium_trades = []
    strong_trades = []
    
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
        
        for i in range(4, len(histogram) - 15):
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
                date_industry_ranks[cache_key] = calculate_stock_rank_on_date(data, trade_date, industry)
            
            rank_dict = date_industry_ranks[cache_key]
            stock_rank = rank_dict.get(stock_code, 0)
            
            if stock_rank < 80:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - 15:
                continue
            
            buy_price = close[buy_idx]
            
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            prev_close_5d = close[buy_idx - 5] if buy_idx >= 5 else close[0]
            prev_close_10d = close[buy_idx - 10] if buy_idx >= 10 else close[0]
            prev_low_20d = np.min(low[buy_idx - 20:buy_idx]) if buy_idx >= 20 else np.min(low[:buy_idx])
            
            ret_5d_before = (buy_price - prev_close_5d) / prev_close_5d * 100
            ret_10d_before = (buy_price - prev_close_10d) / prev_close_10d * 100
            dist_from_low_20d = (buy_price - prev_low_20d) / prev_low_20d * 100
            
            trade_data = {
                'stock_code': stock_code,
                'buy_date': dates[buy_idx],
                'buy_price': buy_price,
                'day1_high_ret': day1_high_ret,
                'histogram': bars[3],
                'vol_ratio': vol_ratio,
                'stock_rank': stock_rank,
                'ret_5d_before': ret_5d_before,
                'ret_10d_before': ret_10d_before,
                'dist_from_low_20d': dist_from_low_20d,
            }
            
            if day1_high_ret < 1:
                weak_trades.append(trade_data)
            elif day1_high_ret < 3:
                medium_trades.append(trade_data)
            else:
                strong_trades.append(trade_data)
    
    print(f"\n共 {len(weak_trades) + len(medium_trades) + len(strong_trades)} 笔交易")
    print(f"  弱势: {len(weak_trades)} 笔")
    print(f"  中势: {len(medium_trades)} 笔")
    print(f"  强势: {len(strong_trades)} 笔")
    
    print("\n" + "="*70)
    print("【买入时特征对比】")
    print("="*70)
    
    features = [
        ('histogram', 'MACD绿柱值'),
        ('vol_ratio', '成交量比'),
        ('stock_rank', '板块排名'),
        ('ret_5d_before', '前5天跌幅%'),
        ('ret_10d_before', '前10天跌幅%'),
        ('dist_from_low_20d', '距20日低点%'),
    ]
    
    print(f"\n{'特征':>15} {'弱势':>12} {'中势':>12} {'强势':>12}")
    print("-"*55)
    
    for key, name in features:
        weak_val = np.mean([t[key] for t in weak_trades]) if weak_trades else 0
        medium_val = np.mean([t[key] for t in medium_trades]) if medium_trades else 0
        strong_val = np.mean([t[key] for t in strong_trades]) if strong_trades else 0
        
        print(f"{name:>15} {weak_val:>12.3f} {medium_val:>12.3f} {strong_val:>12.3f}")
    
    print("\n" + "="*70)
    print("【关键差异分析】")
    print("="*70)
    
    if weak_trades and strong_trades:
        weak_hist = np.array([t['histogram'] for t in weak_trades])
        strong_hist = np.array([t['histogram'] for t in strong_trades])
        
        print(f"\nMACD绿柱值分布:")
        print(f"  弱势: 平均 {np.mean(weak_hist):.4f}, 中位数 {np.median(weak_hist):.4f}")
        print(f"  强势: 平均 {np.mean(strong_hist):.4f}, 中位数 {np.median(strong_hist):.4f}")
        
        weak_vol = np.array([t['vol_ratio'] for t in weak_trades])
        strong_vol = np.array([t['vol_ratio'] for t in strong_trades])
        
        print(f"\n成交量比分布:")
        print(f"  弱势: 平均 {np.mean(weak_vol):.2f}")
        print(f"  强势: 平均 {np.mean(strong_vol):.2f}")
        
        weak_dist = np.array([t['dist_from_low_20d'] for t in weak_trades])
        strong_dist = np.array([t['dist_from_low_20d'] for t in strong_trades])
        
        print(f"\n距20日低点分布:")
        print(f"  弱势: 平均 {np.mean(weak_dist):.2f}%")
        print(f"  强势: 平均 {np.mean(strong_dist):.2f}%")
    
    print("\n" + "="*70)
    print("【预判规则建议】")
    print("="*70)
    
    if weak_trades and strong_trades:
        weak_hist = np.array([t['histogram'] for t in weak_trades])
        strong_hist = np.array([t['histogram'] for t in strong_trades])
        
        hist_overlap = np.sum((weak_hist >= -0.003) & (weak_hist <= -0.002)) / len(weak_hist)
        hist_strong_in_weak = np.sum((strong_hist >= -0.003) & (strong_hist <= -0.002)) / len(strong_hist)
        
        print(f"\n如果用MACD绿柱值 >= -0.003 过滤:")
        print(f"  弱势交易被过滤: {hist_overlap/len(weak_hist)*100:.1f}%")
        print(f"  强势交易被误杀: {hist_strong_in_weak/len(strong_hist)*100:.1f}%")


if __name__ == "__main__":
    analyze_weak_trades()
