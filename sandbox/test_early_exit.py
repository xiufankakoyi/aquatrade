"""
改进策略：前2天快速判断反弹类型

核心思路：
1. 买入后第2天收盘判断：
   - 如果前2天最大涨幅 < 1.5%，判定为小反弹，第2天收盘卖出
   - 否则继续持有，用回撤止盈
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


def test_early_exit_strategy():
    print("\n" + "="*70)
    print("前2天快速判断策略")
    print("="*70)
    print("策略逻辑:")
    print("  - 买入后第2天收盘判断前2天最大涨幅")
    print("  - 如果 < 1.5%，判定为弱反弹，第2天收盘卖出")
    print("  - 否则继续持有，用回撤止盈")
    
    data = get_cache()
    date_industry_ranks = {}
    
    early_exit_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    trailing_stops = [2.0, 3.0, 4.0, 5.0]
    
    print(f"\n{'早退阈值':>8} {'回撤%':>8} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*60)
    
    best_results = []
    
    for early_threshold in early_exit_thresholds:
        for trailing_pct in trailing_stops:
            results = []
            
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
                    
                    max_profit_2d = 0
                    for d in range(1, 3):
                        if buy_idx + d >= len(high):
                            break
                        profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                        if profit > max_profit_2d:
                            max_profit_2d = profit
                    
                    sell_idx = None
                    hold_days = 0
                    
                    if max_profit_2d < early_threshold:
                        sell_idx = buy_idx + 2
                        hold_days = 2
                    else:
                        highest_price = buy_price
                        
                        for d in range(1, 21):
                            if buy_idx + d >= len(close):
                                break
                            
                            current_price = close[buy_idx + d]
                            current_high = high[buy_idx + d]
                            
                            if current_high > highest_price:
                                highest_price = current_high
                            
                            drawdown = (highest_price - current_price) / highest_price * 100
                            if drawdown >= trailing_pct:
                                sell_idx = buy_idx + d
                                hold_days = d
                                break
                    
                    if sell_idx is None:
                        sell_idx = min(buy_idx + 20, len(close) - 1)
                        hold_days = 20
                    
                    sell_price = close[sell_idx]
                    ret = (sell_price - buy_price) / buy_price * 100
                    
                    results.append({
                        'return': ret,
                        'hold_days': hold_days,
                        'max_profit_2d': max_profit_2d,
                    })
            
            if results:
                df = pl.DataFrame(results)
                returns = df['return'].to_numpy()
                
                n = len(returns)
                win_rate = np.sum(returns > 0) / n * 100
                avg_ret = np.mean(returns)
                
                total_profit = np.sum(returns[returns > 0])
                total_loss = np.abs(np.sum(returns[returns < 0]))
                pf = total_profit / total_loss if total_loss > 0 else float('inf')
                
                best_results.append({
                    'early_threshold': early_threshold,
                    'trailing_pct': trailing_pct,
                    'total_trades': n,
                    'win_rate': win_rate,
                    'avg_return': avg_ret,
                    'profit_factor': pf,
                })
                
                print(f"{early_threshold:>7.1f}% {trailing_pct:>7.1f}% {n:>8} {win_rate:>7.1f}% {avg_ret:>+9.2f}% {pf:>8.2f}")
    
    print("\n" + "="*70)
    print("【最佳参数组合 Top 5】")
    print("="*70)
    
    sorted_by_return = sorted(best_results, key=lambda x: x['avg_return'], reverse=True)
    
    for i, r in enumerate(sorted_by_return[:5], 1):
        print(f"\n{i}. 早退阈值={r['early_threshold']}%, 回撤={r['trailing_pct']}%")
        print(f"   平均收益 {r['avg_return']:+.2f}%, 胜率 {r['win_rate']:.1f}%, 盈利因子 {r['profit_factor']:.2f}")
    
    sorted_by_pf = sorted(best_results, key=lambda x: x['profit_factor'], reverse=True)
    
    print("\n【按盈利因子排序 Top 5】")
    for i, r in enumerate(sorted_by_pf[:5], 1):
        print(f"  {i}. 早退阈值={r['early_threshold']}%, 回撤={r['trailing_pct']}%: "
              f"盈利因子 {r['profit_factor']:.2f}, 平均收益 {r['avg_return']:+.2f}%")


if __name__ == "__main__":
    test_early_exit_strategy()
