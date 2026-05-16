"""
左侧买点精确分析

分析指标：
1. 买点离最低点还有几天
2. 买点离最低点的价格距离
3. 买到半山腰的比例
4. 反弹力度
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
from typing import Dict, List

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
        
        try:
            idx = np.where(dates == trade_date)[0]
            if len(idx) == 0:
                continue
            idx = idx[0]
            if idx < 1:
                continue
            
            pct_chg = (close[idx] - close[idx-1]) / close[idx-1] * 100
            stocks_in_industry.append((stock_code, pct_chg))
        except (ValueError, IndexError):
            continue
    
    if not stocks_in_industry:
        return {}
    
    stocks_in_industry.sort(key=lambda x: x[1], reverse=True)
    
    n = len(stocks_in_industry)
    rank_dict = {}
    for i, (stock_code, pct_chg) in enumerate(stocks_in_industry):
        rank_percentile = (n - i) / n * 100
        rank_dict[stock_code] = rank_percentile
    
    return rank_dict


def analyze_left_side_entry():
    print("\n" + "="*70)
    print("左侧买点精确分析")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    days_to_low = []
    price_distance_to_low = []
    bounce_from_low = []
    is_halfway = []
    rebound_strength = []
    
    for stock_code in data.stock_codes:
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
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
            
            search_start = max(0, buy_idx - 20)
            search_end = min(len(close), buy_idx + 30)
            
            local_low_idx = search_start + np.argmin(low[search_start:search_end])
            local_low_price = low[local_low_idx]
            
            days_diff = local_low_idx - buy_idx
            days_to_low.append(days_diff)
            
            price_diff = (buy_price - local_low_price) / local_low_price * 100
            price_distance_to_low.append(price_diff)
            
            if days_diff > 0:
                is_halfway.append(1)
            else:
                is_halfway.append(0)
            
            rebound_window = min(buy_idx + 20, len(close) - 1)
            if rebound_window > local_low_idx:
                rebound = (close[rebound_window] - local_low_price) / local_low_price * 100
                bounce_from_low.append(rebound)
            
            if local_low_idx < buy_idx + 20:
                max_rebound_price = np.max(close[local_low_idx:buy_idx + 20])
                max_rebound = (max_rebound_price - local_low_price) / local_low_price * 100
                rebound_strength.append(max_rebound)
    
    print("\n【买点与最低点的时间距离】")
    print("-"*50)
    days_arr = np.array(days_to_low)
    print(f"  平均: {np.mean(days_arr):.1f} 天")
    print(f"  中位数: {np.median(days_arr):.1f} 天")
    
    print("\n  分布:")
    print(f"    买在最低点当天: {np.sum(days_arr == 0)} 次 ({np.sum(days_arr == 0)/len(days_arr)*100:.1f}%)")
    print(f"    买在最低点前1-3天: {np.sum((days_arr >= 1) & (days_arr <= 3))} 次 ({np.sum((days_arr >= 1) & (days_arr <= 3))/len(days_arr)*100:.1f}%)")
    print(f"    买在最低点前4-7天: {np.sum((days_arr >= 4) & (days_arr <= 7))} 次 ({np.sum((days_arr >= 4) & (days_arr <= 7))/len(days_arr)*100:.1f}%)")
    print(f"    买在最低点前8天以上: {np.sum(days_arr >= 8)} 次 ({np.sum(days_arr >= 8)/len(days_arr)*100:.1f}%)")
    print(f"    买在最低点后(已反弹): {np.sum(days_arr < 0)} 次 ({np.sum(days_arr < 0)/len(days_arr)*100:.1f}%)")
    
    print("\n【买点与最低点的价格距离】")
    print("-"*50)
    price_arr = np.array(price_distance_to_low)
    print(f"  平均: {np.mean(price_arr):.2f}%")
    print(f"  中位数: {np.median(price_arr):.2f}%")
    
    print("\n  分布:")
    print(f"    买在最低点(0%): {np.sum(np.abs(price_arr) < 0.5)} 次 ({np.sum(np.abs(price_arr) < 0.5)/len(price_arr)*100:.1f}%)")
    print(f"    高于最低点0-2%: {np.sum((price_arr >= 0.5) & (price_arr < 2))} 次 ({np.sum((price_arr >= 0.5) & (price_arr < 2))/len(price_arr)*100:.1f}%)")
    print(f"    高于最低点2-5%: {np.sum((price_arr >= 2) & (price_arr < 5))} 次 ({np.sum((price_arr >= 2) & (price_arr < 5))/len(price_arr)*100:.1f}%)")
    print(f"    高于最低点5-10%: {np.sum((price_arr >= 5) & (price_arr < 10))} 次 ({np.sum((price_arr >= 5) & (price_arr < 10))/len(price_arr)*100:.1f}%)")
    print(f"    高于最低点10%以上: {np.sum(price_arr >= 10)} 次 ({np.sum(price_arr >= 10)/len(price_arr)*100:.1f}%)")
    
    print("\n【半山腰分析】")
    print("-"*50)
    halfway_arr = np.array(is_halfway)
    print(f"  买到半山腰(最低点还没到): {np.sum(halfway_arr)} 次 ({np.mean(halfway_arr)*100:.1f}%)")
    print(f"  买在底部区域(最低点已过): {np.sum(1 - halfway_arr)} 次 ({np.mean(1 - halfway_arr)*100:.1f}%)")
    
    print("\n【反弹力度分析】")
    print("-"*50)
    if bounce_from_low:
        bounce_arr = np.array(bounce_from_low)
        print(f"  从最低点反弹20天后的收益:")
        print(f"    平均: {np.mean(bounce_arr):.2f}%")
        print(f"    中位数: {np.median(bounce_arr):.2f}%")
        print(f"    正收益比例: {np.sum(bounce_arr > 0)/len(bounce_arr)*100:.1f}%")
    
    if rebound_strength:
        rebound_arr = np.array(rebound_strength)
        print(f"\n  从最低点的最大反弹幅度:")
        print(f"    平均: {np.mean(rebound_arr):.2f}%")
        print(f"    中位数: {np.median(rebound_arr):.2f}%")
        print(f"    >5%的比例: {np.sum(rebound_arr > 5)/len(rebound_arr)*100:.1f}%")
        print(f"    >10%的比例: {np.sum(rebound_arr > 10)/len(rebound_arr)*100:.1f}%")
        print(f"    >20%的比例: {np.sum(rebound_arr > 20)/len(rebound_arr)*100:.1f}%")
    
    print("\n【信号强度评估】")
    print("="*50)
    
    buy_at_bottom = np.sum(days_arr <= 0)
    buy_near_bottom = np.sum((days_arr >= 1) & (days_arr <= 3) & (price_arr < 5))
    buy_halfway = np.sum((days_arr > 3) | (price_arr >= 5))
    
    print(f"  买在底部/刚反弹: {buy_at_bottom} 次 ({buy_at_bottom/len(days_arr)*100:.1f}%)")
    print(f"  买在底部附近(1-3天, <5%): {buy_near_bottom} 次 ({buy_near_bottom/len(days_arr)*100:.1f}%)")
    print(f"  买在半山腰: {buy_halfway} 次 ({buy_halfway/len(days_arr)*100:.1f}%)")
    
    quality_rate = (buy_at_bottom + buy_near_bottom) / len(days_arr) * 100
    print(f"\n  ✅ 优质买点比例: {quality_rate:.1f}%")
    
    if quality_rate > 60:
        print("  结论: 买点质量较好，多数买在底部区域")
    elif quality_rate > 40:
        print("  结论: 买点质量一般，有一定比例买到半山腰")
    else:
        print("  结论: 买点质量较差，容易买到半山腰")


if __name__ == "__main__":
    analyze_left_side_entry()
