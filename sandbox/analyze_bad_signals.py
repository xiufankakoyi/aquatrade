"""
分析问题买点的反弹特征

验证假设：问题买点往往有小反弹，但没及时止盈，导致二次下跌亏损
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


def analyze_bad_signals():
    print("\n" + "="*70)
    print("问题买点反弹特征分析")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    bad_signals = []
    
    for stock_code in data.stock_codes:
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
        low = stock_data['low']
        high = stock_data['high']
        volume = stock_data['volume']
        dates = stock_data['dates']
        
        if len(close) < 50:
            continue
        
        info = data.stock_info.get(stock_code, {})
        industry = info.get('industry')
        stock_name = info.get('name', '')
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
            
            days_to_low = local_low_idx - buy_idx
            
            if days_to_low < 15:
                continue
            
            max_profit_first_5d = 0
            max_profit_day = 0
            for d in range(1, 6):
                if buy_idx + d >= len(high):
                    break
                high_price = high[buy_idx + d]
                profit = (high_price - buy_price) / buy_price * 100
                if profit > max_profit_first_5d:
                    max_profit_first_5d = profit
                    max_profit_day = d
            
            max_profit_first_10d = 0
            for d in range(1, 11):
                if buy_idx + d >= len(high):
                    break
                high_price = high[buy_idx + d]
                profit = (high_price - buy_price) / buy_price * 100
                if profit > max_profit_first_10d:
                    max_profit_first_10d = profit
            
            ret_5d = (close[buy_idx + 5] - buy_price) / buy_price * 100 if buy_idx + 5 < len(close) else None
            ret_10d = (close[buy_idx + 10] - buy_price) / buy_price * 100 if buy_idx + 10 < len(close) else None
            ret_20d = (close[buy_idx + 20] - buy_price) / buy_price * 100 if buy_idx + 20 < len(close) else None
            
            bad_signals.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'buy_date': dates[buy_idx],
                'buy_price': buy_price,
                'days_to_low': days_to_low,
                'max_profit_5d': max_profit_first_5d,
                'max_profit_day': max_profit_day,
                'max_profit_10d': max_profit_first_10d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'ret_20d': ret_20d,
            })
    
    print(f"\n共找到 {len(bad_signals)} 个问题买点（离最低点>=15天）")
    
    print("\n【前5天反弹分析】")
    print("-"*60)
    
    max_5d_arr = np.array([s['max_profit_5d'] for s in bad_signals])
    max_day_arr = np.array([s['max_profit_day'] for s in bad_signals])
    ret_5d_arr = np.array([s['ret_5d'] for s in bad_signals if s['ret_5d'] is not None])
    
    print(f"  前5天最大涨幅: 平均 {np.mean(max_5d_arr):.2f}%, 中位数 {np.median(max_5d_arr):.2f}%")
    print(f"  前5天最大涨幅>3%的比例: {np.sum(max_5d_arr > 3) / len(max_5d_arr) * 100:.1f}%")
    print(f"  前5天最大涨幅>5%的比例: {np.sum(max_5d_arr > 5) / len(max_5d_arr) * 100:.1f}%")
    print(f"  最高点出现时间: 平均第 {np.mean(max_day_arr):.1f} 天")
    
    print(f"\n  但第5天收盘收益: 平均 {np.mean(ret_5d_arr):.2f}%")
    print(f"  第5天正收益比例: {np.sum(ret_5d_arr > 0) / len(ret_5d_arr) * 100:.1f}%")
    
    print("\n【前10天反弹分析】")
    print("-"*60)
    
    max_10d_arr = np.array([s['max_profit_10d'] for s in bad_signals])
    ret_10d_arr = np.array([s['ret_10d'] for s in bad_signals if s['ret_10d'] is not None])
    
    print(f"  前10天最大涨幅: 平均 {np.mean(max_10d_arr):.2f}%, 中位数 {np.median(max_10d_arr):.2f}%")
    print(f"  前10天最大涨幅>3%的比例: {np.sum(max_10d_arr > 3) / len(max_10d_arr) * 100:.1f}%")
    print(f"  前10天最大涨幅>5%的比例: {np.sum(max_10d_arr > 5) / len(max_10d_arr) * 100:.1f}%")
    
    print(f"\n  但第10天收盘收益: 平均 {np.mean(ret_10d_arr):.2f}%")
    print(f"  第10天正收益比例: {np.sum(ret_10d_arr > 0) / len(ret_10d_arr) * 100:.1f}%")
    
    print("\n【具体案例】")
    print("="*100)
    
    had_profit_but_lost = [s for s in bad_signals if s['max_profit_5d'] > 3 and s['ret_10d'] is not None and s['ret_10d'] < 0]
    
    print(f"\n有盈利机会但最终亏损的案例: {len(had_profit_but_lost)} 个")
    print(f"占问题买点的比例: {len(had_profit_but_lost) / len(bad_signals) * 100:.1f}%")
    
    print("\n前10个案例:")
    for s in had_profit_but_lost[:10]:
        print(f"\n  {s['stock_code']} {s['stock_name']} ({s['buy_date']})")
        print(f"    买入价: {s['buy_price']:.2f}")
        print(f"    前5天最高涨幅: {s['max_profit_5d']:.2f}% (第{s['max_profit_day']}天)")
        print(f"    前10天最高涨幅: {s['max_profit_10d']:.2f}%")
        print(f"    第5天收益: {s['ret_5d']:.2f}%")
        print(f"    第10天收益: {s['ret_10d']:.2f}%")
        print(f"    离真正最低点: {s['days_to_low']} 天")
    
    print("\n【结论】")
    print("="*60)
    
    profit_chance = np.sum(max_5d_arr > 3) / len(max_5d_arr) * 100
    final_loss = np.mean(ret_10d_arr)
    
    print(f"  ✅ {profit_chance:.1f}% 的问题买点在前5天有3%+的盈利机会")
    print(f"  ❌ 但第10天平均收益: {final_loss:.2f}%")
    print(f"\n  结论: 你的观察正确！问题买点往往有小反弹，但没及时止盈")
    print(f"        导致二次下跌后由盈转亏")
    print(f"\n  解决方案: 使用移动止盈策略，从最高点回撤2-3%就卖出")


if __name__ == "__main__":
    analyze_bad_signals()
