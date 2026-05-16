"""
测试移动止盈策略

策略：买入后，从最高点回撤X%就卖出
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


def test_trailing_take_profit():
    print("\n" + "="*70)
    print("移动止盈策略测试")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    trailing_pcts = [2, 3, 4, 5, 6, 8, 10]
    min_profit_thresholds = [0, 2, 3, 5]
    
    results_by_params = {}
    
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
            
            for trailing_pct in trailing_pcts:
                for min_profit in min_profit_thresholds:
                    key = (trailing_pct, min_profit)
                    if key not in results_by_params:
                        results_by_params[key] = []
                    
                    highest_price = buy_price
                    max_profit = 0
                    sell_idx = None
                    
                    for d in range(1, 21):
                        if buy_idx + d >= len(close):
                            break
                        
                        current_price = close[buy_idx + d]
                        current_high = high[buy_idx + d]
                        
                        if current_high > highest_price:
                            highest_price = current_high
                        
                        current_profit = (current_price - buy_price) / buy_price * 100
                        max_profit = max(max_profit, (highest_price - buy_price) / buy_price * 100)
                        
                        if max_profit >= min_profit:
                            drawdown = (highest_price - current_price) / highest_price * 100
                            if drawdown >= trailing_pct:
                                sell_idx = buy_idx + d
                                break
                    
                    if sell_idx is None:
                        sell_idx = min(buy_idx + 20, len(close) - 1)
                    
                    sell_price = close[sell_idx]
                    ret = (sell_price - buy_price) / buy_price * 100
                    
                    results_by_params[key].append(ret)
    
    print("\n【移动止盈策略结果】")
    print("="*100)
    print(f"{'回撤%':>6} {'最小盈利%':>10} {'交易数':>8} {'平均收益':>10} {'胜率':>8} {'盈利因子':>8}")
    print("-"*100)
    
    sorted_results = []
    
    for (trailing_pct, min_profit), returns in results_by_params.items():
        if not returns:
            continue
        
        arr = np.array(returns)
        n = len(arr)
        win_count = np.sum(arr > 0)
        win_rate = win_count / n * 100
        avg_ret = np.mean(arr)
        
        total_profit = np.sum(arr[arr > 0])
        total_loss = np.abs(np.sum(arr[arr < 0]))
        pf = total_profit / total_loss if total_loss > 0 else float('inf')
        
        sorted_results.append((trailing_pct, min_profit, n, avg_ret, win_rate, pf))
        
        print(f"{trailing_pct:>6}% {min_profit:>10}% {n:>8} {avg_ret:>+9.2f}% {win_rate:>7.1f}% {pf:>8.2f}")
    
    print("\n" + "="*100)
    print("最佳参数组合")
    print("="*100)
    
    sorted_by_ret = sorted(sorted_results, key=lambda x: x[3], reverse=True)
    
    print("\n【按平均收益排序 Top 5】")
    for i, (trailing, min_profit, n, avg_ret, win_rate, pf) in enumerate(sorted_by_ret[:5], 1):
        print(f"  {i}. 回撤{trailing}%止盈(最小盈利{min_profit}%): 平均收益 {avg_ret:+.2f}%, 胜率 {win_rate:.1f}%, 盈利因子 {pf:.2f}")
    
    sorted_by_pf = sorted(sorted_results, key=lambda x: x[5], reverse=True)
    
    print("\n【按盈利因子排序 Top 5】")
    for i, (trailing, min_profit, n, avg_ret, win_rate, pf) in enumerate(sorted_by_pf[:5], 1):
        print(f"  {i}. 回撤{trailing}%止盈(最小盈利{min_profit}%): 盈利因子 {pf:.2f}, 平均收益 {avg_ret:+.2f}%, 胜率 {win_rate:.1f}%")


if __name__ == "__main__":
    test_trailing_take_profit()
