"""
深入分析策略失败的原因

检查点：
1. 买点是否真的有效？（买入后涨跌分布）
2. 持仓时间对收益的影响
3. 不同市场环境下的表现
4. 是否存在参数优化空间
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


def analyze_buy_point():
    print("\n" + "="*70)
    print("买点深度分析")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    results_1d = []
    results_3d = []
    results_5d = []
    results_10d = []
    results_20d = []
    
    max_profit_results = []
    
    for stock_code in data.stock_codes:
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
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
        
        for i in range(4, len(histogram) - 25):
            bars = histogram[i-3:i+1]
            
            if not np.all(bars < 0):
                continue
            if not (bars[0] < bars[1] < bars[2] < bars[3]):
                continue
            
            diff1 = bars[1] - bars[0]
            diff2 = bars[2] - bars[1]
            diff3 = bars[3] - bars[2]
            if not (diff1 < diff2 < diff3):
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
            
            if buy_idx + 1 < len(close):
                ret_1d = (close[buy_idx + 1] - buy_price) / buy_price * 100
                results_1d.append(ret_1d)
            
            if buy_idx + 3 < len(close):
                ret_3d = (close[buy_idx + 3] - buy_price) / buy_price * 100
                results_3d.append(ret_3d)
            
            if buy_idx + 5 < len(close):
                ret_5d = (close[buy_idx + 5] - buy_price) / buy_price * 100
                results_5d.append(ret_5d)
            
            if buy_idx + 10 < len(close):
                ret_10d = (close[buy_idx + 10] - buy_price) / buy_price * 100
                results_10d.append(ret_10d)
            
            if buy_idx + 20 < len(close):
                ret_20d = (close[buy_idx + 20] - buy_price) / buy_price * 100
                results_20d.append(ret_20d)
            
            max_high = np.max(high[buy_idx:buy_idx+20]) if buy_idx + 20 < len(high) else np.max(high[buy_idx:])
            max_profit = (max_high - buy_price) / buy_price * 100
            max_profit_results.append(max_profit)
    
    print("\n【持仓时间 vs 收益】")
    print("-"*50)
    
    for days, results in [(1, results_1d), (3, results_3d), (5, results_5d), (10, results_10d), (20, results_20d)]:
        if results:
            arr = np.array(results)
            win_rate = np.sum(arr > 0) / len(arr) * 100
            avg_ret = np.mean(arr)
            median_ret = np.median(arr)
            print(f"  持仓{days:2d}天: 平均收益 {avg_ret:+.2f}%, 中位数 {median_ret:+.2f}%, 胜率 {win_rate:.1f}%")
    
    print("\n【最大潜在收益】")
    print("-"*50)
    if max_profit_results:
        arr = np.array(max_profit_results)
        print(f"  20天内最大涨幅: 平均 {np.mean(arr):.2f}%, 中位数 {np.median(arr):.2f}%")
        print(f"  最大涨幅>5%的比例: {np.sum(arr > 5) / len(arr) * 100:.1f}%")
        print(f"  最大涨幅>10%的比例: {np.sum(arr > 10) / len(arr) * 100:.1f}%")
        print(f"  最大涨幅>20%的比例: {np.sum(arr > 20) / len(arr) * 100:.1f}%")
    
    print("\n【收益分布】")
    print("-"*50)
    
    for days, results in [(3, results_3d), (20, results_20d)]:
        if results:
            arr = np.array(results)
            print(f"\n  持仓{days}天收益分布:")
            print(f"    >10%: {np.sum(arr > 10):4d} ({np.sum(arr > 10)/len(arr)*100:.1f}%)")
            print(f"    5-10%: {np.sum((arr > 5) & (arr <= 10)):4d} ({np.sum((arr > 5) & (arr <= 10))/len(arr)*100:.1f}%)")
            print(f"    0-5%: {np.sum((arr > 0) & (arr <= 5)):4d} ({np.sum((arr > 0) & (arr <= 5))/len(arr)*100:.1f}%)")
            print(f"    -5-0%: {np.sum((arr >= -5) & (arr <= 0)):4d} ({np.sum((arr >= -5) & (arr <= 0))/len(arr)*100:.1f}%)")
            print(f"    -10--5%: {np.sum((arr >= -10) & (arr < -5)):4d} ({np.sum((arr >= -10) & (arr < -5))/len(arr)*100:.1f}%)")
            print(f"    <-10%: {np.sum(arr < -10):4d} ({np.sum(arr < -10)/len(arr)*100:.1f}%)")
    
    print("\n【结论】")
    print("="*50)
    
    if results_3d:
        arr_3d = np.array(results_3d)
        if np.mean(arr_3d) > 0:
            print("  ✅ 买点有效：3天平均收益为正")
        else:
            print("  ❌ 买点无效：3天平均收益为负")
        
        if np.mean(arr_3d) > 0 and np.median(arr_3d) < 0:
            print("  ⚠️  注意：平均收益为正但中位数为负，说明少数大盈利拉高了平均")
        
        if max_profit_results:
            arr_max = np.array(max_profit_results)
            if np.mean(arr_max) > 10:
                print(f"  💡 潜力：20天内平均最大涨幅 {np.mean(arr_max):.1f}%，说明有盈利空间")
                print("     问题可能在于卖点无法锁定利润")


if __name__ == "__main__":
    analyze_buy_point()
