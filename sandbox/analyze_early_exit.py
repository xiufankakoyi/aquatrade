"""
分析早退交易如果继续持有会怎样
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


def analyze_early_exit():
    print("\n" + "="*70)
    print("早退策略问题分析")
    print("="*70)
    
    data = get_cache()
    date_industry_ranks = {}
    
    early_exit_trades = []
    continue_hold_trades = []
    
    for stock_code in data.stock_codes:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
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
            
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            day1_close = close[buy_idx + 1] if buy_idx + 1 < len(close) else buy_price
            day1_close_ret = (day1_close - buy_price) / buy_price * 100
            
            day2_high = high[buy_idx + 2] if buy_idx + 2 < len(high) else buy_price
            day2_high_ret = (day2_high - buy_price) / buy_price * 100
            day2_close = close[buy_idx + 2] if buy_idx + 2 < len(close) else buy_price
            day2_close_ret = (day2_close - buy_price) / buy_price * 100
            
            max_high_2d = max(day1_high_ret, day2_high_ret)
            
            ret_3d = (close[buy_idx + 3] - buy_price) / buy_price * 100 if buy_idx + 3 < len(close) else None
            ret_5d = (close[buy_idx + 5] - buy_price) / buy_price * 100 if buy_idx + 5 < len(close) else None
            ret_10d = (close[buy_idx + 10] - buy_price) / buy_price * 100 if buy_idx + 10 < len(close) else None
            
            max_high_5d = 0
            for d in range(1, 6):
                if buy_idx + d >= len(high):
                    break
                profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                if profit > max_high_5d:
                    max_high_5d = profit
            
            trade_data = {
                'day1_high_ret': day1_high_ret,
                'day1_close_ret': day1_close_ret,
                'day2_high_ret': day2_high_ret,
                'day2_close_ret': day2_close_ret,
                'max_high_2d': max_high_2d,
                'day2_sell_ret': day2_close_ret,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'max_high_5d': max_high_5d,
            }
            
            if day1_high_ret >= 1 and max_high_2d >= 2:
                continue_hold_trades.append(trade_data)
            else:
                early_exit_trades.append(trade_data)
    
    print(f"\n早退交易: {len(early_exit_trades)} 笔")
    print(f"继续持有交易: {len(continue_hold_trades)} 笔")
    
    print("\n" + "="*70)
    print("【早退交易分析】")
    print("="*70)
    
    if early_exit_trades:
        print("\n第1天、第2天的情况:")
        day1_close_arr = np.array([t['day1_close_ret'] for t in early_exit_trades])
        day2_close_arr = np.array([t['day2_close_ret'] for t in early_exit_trades])
        
        print(f"  第1天收盘收益: 平均 {np.mean(day1_close_arr):.2f}%")
        print(f"  第2天收盘收益: 平均 {np.mean(day2_close_arr):.2f}%")
        
        print("\n如果继续持有到第3、5、10天:")
        ret_3d_arr = np.array([t['ret_3d'] for t in early_exit_trades if t['ret_3d'] is not None])
        ret_5d_arr = np.array([t['ret_5d'] for t in early_exit_trades if t['ret_5d'] is not None])
        ret_10d_arr = np.array([t['ret_10d'] for t in early_exit_trades if t['ret_10d'] is not None])
        
        if len(ret_3d_arr) > 0:
            print(f"  第3天收益: 平均 {np.mean(ret_3d_arr):.2f}%")
        if len(ret_5d_arr) > 0:
            print(f"  第5天收益: 平均 {np.mean(ret_5d_arr):.2f}%")
        if len(ret_10d_arr) > 0:
            print(f"  第10天收益: 平均 {np.mean(ret_10d_arr):.2f}%")
        
        print("\n前5天最大涨幅:")
        max_high_5d_arr = np.array([t['max_high_5d'] for t in early_exit_trades])
        print(f"  平均: {np.mean(max_high_5d_arr):.2f}%")
        print(f"  >3%比例: {np.sum(max_high_5d_arr > 3) / len(max_high_5d_arr) * 100:.1f}%")
        print(f"  >5%比例: {np.sum(max_high_5d_arr > 5) / len(max_high_5d_arr) * 100:.1f}%")
    
    print("\n" + "="*70)
    print("【继续持有交易分析】")
    print("="*70)
    
    if continue_hold_trades:
        print("\n第1天、第2天的情况:")
        day1_close_arr = np.array([t['day1_close_ret'] for t in continue_hold_trades])
        day2_close_arr = np.array([t['day2_close_ret'] for t in continue_hold_trades])
        
        print(f"  第1天收盘收益: 平均 {np.mean(day1_close_arr):.2f}%")
        print(f"  第2天收盘收益: 平均 {np.mean(day2_close_arr):.2f}%")
        
        print("\n继续持有到第3、5、10天:")
        ret_3d_arr = np.array([t['ret_3d'] for t in continue_hold_trades if t['ret_3d'] is not None])
        ret_5d_arr = np.array([t['ret_5d'] for t in continue_hold_trades if t['ret_5d'] is not None])
        ret_10d_arr = np.array([t['ret_10d'] for t in continue_hold_trades if t['ret_10d'] is not None])
        
        if len(ret_3d_arr) > 0:
            print(f"  第3天收益: 平均 {np.mean(ret_3d_arr):.2f}%")
        if len(ret_5d_arr) > 0:
            print(f"  第5天收益: 平均 {np.mean(ret_5d_arr):.2f}%")
        if len(ret_10d_arr) > 0:
            print(f"  第10天收益: 平均 {np.mean(ret_10d_arr):.2f}%")
    
    print("\n" + "="*70)
    print("【关键问题】")
    print("="*70)
    
    if early_exit_trades:
        max_high_5d_arr = np.array([t['max_high_5d'] for t in early_exit_trades])
        has_profit_chance = np.sum(max_high_5d_arr > 2) / len(max_high_5d_arr) * 100
        
        print(f"\n早退交易中，前5天有>2%涨幅机会的比例: {has_profit_chance:.1f}%")
        
        if has_profit_chance > 30:
            print("\n⚠️  早退可能过早，错失了一些盈利机会")


if __name__ == "__main__":
    analyze_early_exit()
