"""
输出清晰的买点案例供K线图验证
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


def main():
    print("\n" + "="*80)
    print("买点信号案例 - 供K线图验证")
    print("="*80)
    
    data = get_cache()
    
    date_industry_ranks = {}
    
    signals = []
    
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
            
            signal_date = dates[i]
            buy_date = dates[buy_idx]
            
            signal_close = close[i]
            buy_close = close[buy_idx]
            
            search_start = max(0, buy_idx - 20)
            search_end = min(len(close), buy_idx + 30)
            local_low_idx = search_start + np.argmin(low[search_start:search_end])
            local_low_date = dates[local_low_idx]
            local_low_price = low[local_low_idx]
            
            days_to_low = local_low_idx - buy_idx
            price_to_low = (buy_close - local_low_price) / local_low_price * 100
            
            ret_5d = (close[buy_idx + 5] - buy_close) / buy_close * 100 if buy_idx + 5 < len(close) else None
            ret_10d = (close[buy_idx + 10] - buy_close) / buy_close * 100 if buy_idx + 10 < len(close) else None
            
            max_high_10d = np.max(high[buy_idx:buy_idx+10]) if buy_idx + 10 < len(high) else np.max(high[buy_idx:])
            max_profit = (max_high_10d - buy_close) / buy_close * 100
            
            signals.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'industry': industry,
                'signal_date': signal_date,
                'buy_date': buy_date,
                'signal_close': signal_close,
                'buy_close': buy_close,
                'local_low_date': local_low_date,
                'local_low_price': local_low_price,
                'days_to_low': days_to_low,
                'price_to_low': price_to_low,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'max_profit': max_profit,
                'bars': bars,
            })
    
    print(f"\n共找到 {len(signals)} 个买点信号")
    
    print("\n" + "="*100)
    print("【优质案例 - 买在最低点附近】")
    print("="*100)
    
    good_signals = [s for s in signals if abs(s['days_to_low']) <= 2]
    good_signals = sorted(good_signals, key=lambda x: x['signal_date'], reverse=True)[:5]
    
    for s in good_signals:
        print(f"\n股票: {s['stock_code']} {s['stock_name']} ({s['industry']})")
        print(f"  ────────────────────────────────────────")
        print(f"  信号日: {s['signal_date']}  收盘价: {s['signal_close']:.2f}")
        print(f"  买入日: {s['buy_date']}      收盘价: {s['buy_close']:.2f}")
        print(f"  最低点: {s['local_low_date']}  最低价: {s['local_low_price']:.2f}")
        print(f"  离最低点: {s['days_to_low']} 天")
        print(f"  MACD绿柱(前4天): {s['bars'][0]:.4f} → {s['bars'][1]:.4f} → {s['bars'][2]:.4f} → {s['bars'][3]:.4f}")
        print(f"  5天收益: {s['ret_5d']:+.2f}%  10天收益: {s['ret_10d']:+.2f}%  最大涨幅: {s['max_profit']:+.2f}%")
    
    print("\n" + "="*100)
    print("【问题案例 - 离最低点很远】")
    print("="*100)
    
    bad_signals = [s for s in signals if s['days_to_low'] >= 20]
    bad_signals = sorted(bad_signals, key=lambda x: x['signal_date'], reverse=True)[:5]
    
    for s in bad_signals:
        print(f"\n股票: {s['stock_code']} {s['stock_name']} ({s['industry']})")
        print(f"  ────────────────────────────────────────")
        print(f"  信号日: {s['signal_date']}  收盘价: {s['signal_close']:.2f}")
        print(f"  买入日: {s['buy_date']}      收盘价: {s['buy_close']:.2f}")
        print(f"  最低点: {s['local_low_date']}  最低价: {s['local_low_price']:.2f}")
        print(f"  离最低点: {s['days_to_low']} 天 (价格距离: {s['price_to_low']:.1f}%)")
        print(f"  MACD绿柱(前4天): {s['bars'][0]:.4f} → {s['bars'][1]:.4f} → {s['bars'][2]:.4f} → {s['bars'][3]:.4f}")
        print(f"  5天收益: {s['ret_5d']:+.2f}%  10天收益: {s['ret_10d']:+.2f}%  最大涨幅: {s['max_profit']:+.2f}%")


if __name__ == "__main__":
    main()
