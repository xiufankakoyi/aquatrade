"""
分析买点后的价格走势特征

目标：找出最佳卖出时机
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


def analyze_price_pattern():
    print("\n" + "="*70)
    print("买点后价格走势分析")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    daily_returns = {i: [] for i in range(1, 21)}
    high_day = []
    max_profit_before_dip = []
    
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
            
            for day in range(1, 21):
                if buy_idx + day < len(close):
                    ret = (close[buy_idx + day] - buy_price) / buy_price * 100
                    daily_returns[day].append(ret)
            
            high_idx = buy_idx + 1
            max_high = high[buy_idx + 1]
            for d in range(1, 21):
                if buy_idx + d >= len(high):
                    break
                if high[buy_idx + d] > max_high:
                    max_high = high[buy_idx + d]
                    high_idx = buy_idx + d
            high_day.append(high_idx - buy_idx)
            
            max_profit = 0
            current_high = buy_price
            for d in range(1, 21):
                if buy_idx + d >= len(close):
                    break
                if close[buy_idx + d] > current_high:
                    current_high = close[buy_idx + d]
                profit = (current_high - buy_price) / buy_price * 100
                if profit > max_profit:
                    max_profit = profit
                elif profit < max_profit - 3:
                    break
            max_profit_before_dip.append(max_profit)
    
    print("\n【每日收益变化】")
    print("-"*50)
    print(f"{'天数':>4} {'平均收益':>10} {'胜率':>8} {'正收益次数':>10}")
    print("-"*50)
    
    for day in range(1, 21):
        if daily_returns[day]:
            arr = np.array(daily_returns[day])
            avg_ret = np.mean(arr)
            win_rate = np.sum(arr > 0) / len(arr) * 100
            pos_count = np.sum(arr > 0)
            print(f"{day:>4} {avg_ret:>+9.2f}% {win_rate:>7.1f}% {pos_count:>10}")
    
    print("\n【最高点出现时间】")
    print("-"*50)
    high_day_arr = np.array(high_day)
    print(f"  平均在第 {np.mean(high_day_arr):.1f} 天达到最高点")
    print(f"  中位数在第 {np.median(high_day_arr):.1f} 天达到最高点")
    
    print("\n  分布:")
    for d in [1, 2, 3, 5, 7, 10, 15, 20]:
        count = np.sum(high_day_arr == d)
        pct = count / len(high_day_arr) * 100
        print(f"    第{d:2d}天: {count:4d} 次 ({pct:.1f}%)")
    
    print("\n【回撤前最大盈利】")
    print("-"*50)
    if max_profit_before_dip:
        arr = np.array(max_profit_before_dip)
        print(f"  平均: {np.mean(arr):.2f}%")
        print(f"  中位数: {np.median(arr):.2f}%")
        print(f"  >3%: {np.sum(arr > 3) / len(arr) * 100:.1f}%")
        print(f"  >5%: {np.sum(arr > 5) / len(arr) * 100:.1f}%")
        print(f"  >8%: {np.sum(arr > 8) / len(arr) * 100:.1f}%")
    
    print("\n【策略建议】")
    print("="*50)
    
    avg_rets = [np.mean(daily_returns[d]) for d in range(1, 21) if daily_returns[d]]
    best_day = np.argmax(avg_rets) + 1
    best_ret = avg_rets[best_day - 1]
    
    print(f"  最佳持仓天数: {best_day} 天 (平均收益 {best_ret:+.2f}%)")
    
    if best_ret < 0:
        print("\n  ⚠️  所有持仓天数都是负收益，买点需要改进")
    else:
        print(f"\n  💡 建议持仓 {best_day} 天后卖出")
    
    print(f"\n  💡 如果使用移动止盈，建议设置 3-5% 回撤止盈")
    print(f"     因为平均最大涨幅 {np.mean(max_profit_before_dip):.1f}%，但最终收益为负")


if __name__ == "__main__":
    analyze_price_pattern()
