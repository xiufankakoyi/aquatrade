"""
细化卖点分析：小反弹 vs 大反弹

目标：
1. 分析买点后3天的反弹特征
2. 区分小反弹和大反弹
3. 测试主板票 + MACD阈值 + 回撤止盈
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


def analyze_rebound_patterns():
    print("\n" + "="*70)
    print("小反弹 vs 大反弹分析")
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
            max_profit_day_3d = 0
            for d in range(1, 4):
                if buy_idx + d >= len(high):
                    break
                profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                if profit > max_profit_3d:
                    max_profit_3d = profit
                    max_profit_day_3d = d
            
            max_profit_5d = 0
            for d in range(1, 6):
                if buy_idx + d >= len(high):
                    break
                profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                if profit > max_profit_5d:
                    max_profit_5d = profit
            
            max_profit_10d = 0
            for d in range(1, 11):
                if buy_idx + d >= len(high):
                    break
                profit = (high[buy_idx + d] - buy_price) / buy_price * 100
                if profit > max_profit_10d:
                    max_profit_10d = profit
            
            ret_3d = (close[buy_idx + 3] - buy_price) / buy_price * 100 if buy_idx + 3 < len(close) else None
            ret_5d = (close[buy_idx + 5] - buy_price) / buy_price * 100 if buy_idx + 5 < len(close) else None
            ret_10d = (close[buy_idx + 10] - buy_price) / buy_price * 100 if buy_idx + 10 < len(close) else None
            
            trades.append({
                'stock_code': stock_code,
                'buy_date': dates[buy_idx],
                'buy_price': buy_price,
                'max_profit_3d': max_profit_3d,
                'max_profit_day_3d': max_profit_day_3d,
                'max_profit_5d': max_profit_5d,
                'max_profit_10d': max_profit_10d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'histogram': bars[3],
            })
    
    print(f"\n共 {len(trades)} 笔交易（主板 + MACD阈值-0.01）")
    
    print("\n" + "="*70)
    print("【买点后3天反弹分析】")
    print("="*70)
    
    max_3d_arr = np.array([t['max_profit_3d'] for t in trades])
    ret_3d_arr = np.array([t['ret_3d'] for t in trades if t['ret_3d'] is not None])
    
    print(f"\n前3天最大涨幅:")
    print(f"  平均: {np.mean(max_3d_arr):.2f}%")
    print(f"  中位数: {np.median(max_3d_arr):.2f}%")
    print(f"  >3%比例: {np.sum(max_3d_arr > 3) / len(max_3d_arr) * 100:.1f}%")
    print(f"  >5%比例: {np.sum(max_3d_arr > 5) / len(max_3d_arr) * 100:.1f}%")
    
    print(f"\n第3天收盘收益:")
    print(f"  平均: {np.mean(ret_3d_arr):.2f}%")
    print(f"  正收益比例: {np.sum(ret_3d_arr > 0) / len(ret_3d_arr) * 100:.1f}%")
    
    print("\n" + "="*70)
    print("【小反弹 vs 大反弹分类】")
    print("="*70)
    
    small_rebound = [t for t in trades if t['max_profit_3d'] <= 3]
    medium_rebound = [t for t in trades if 3 < t['max_profit_3d'] <= 8]
    large_rebound = [t for t in trades if t['max_profit_3d'] > 8]
    
    print(f"\n小反弹 (≤3%): {len(small_rebound)} 笔 ({len(small_rebound)/len(trades)*100:.1f}%)")
    if small_rebound:
        ret_arr = np.array([t['ret_3d'] for t in small_rebound if t['ret_3d'] is not None])
        print(f"  第3天平均收益: {np.mean(ret_arr):.2f}%")
        print(f"  正收益比例: {np.sum(ret_arr > 0) / len(ret_arr) * 100:.1f}%")
    
    print(f"\n中反弹 (3-8%): {len(medium_rebound)} 笔 ({len(medium_rebound)/len(trades)*100:.1f}%)")
    if medium_rebound:
        ret_arr = np.array([t['ret_3d'] for t in medium_rebound if t['ret_3d'] is not None])
        print(f"  第3天平均收益: {np.mean(ret_arr):.2f}%")
        print(f"  正收益比例: {np.sum(ret_arr > 0) / len(ret_arr) * 100:.1f}%")
    
    print(f"\n大反弹 (>8%): {len(large_rebound)} 笔 ({len(large_rebound)/len(trades)*100:.1f}%)")
    if large_rebound:
        ret_arr = np.array([t['ret_3d'] for t in large_rebound if t['ret_3d'] is not None])
        print(f"  第3天平均收益: {np.mean(ret_arr):.2f}%")
        print(f"  正收益比例: {np.sum(ret_arr > 0) / len(ret_arr) * 100:.1f}%")
    
    print("\n" + "="*70)
    print("【卖点策略测试：主板 + MACD阈值 + 回撤止盈】")
    print("="*70)
    
    print(f"\n{'回撤%':>8} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8} {'平均持仓':>8}")
    print("-"*60)
    
    for trailing_pct in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        results = []
        
        for t in trades:
            buy_idx = None
            stock_data = data.daily_data[t['stock_code']]
            dates = stock_data['dates']
            close = stock_data['close']
            high = stock_data['high']
            
            for idx, d in enumerate(dates):
                if d == t['buy_date']:
                    buy_idx = idx
                    break
            
            if buy_idx is None:
                continue
            
            buy_price = close[buy_idx]
            highest_price = buy_price
            sell_idx = None
            
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
                    break
            
            if sell_idx is None:
                sell_idx = min(buy_idx + 20, len(close) - 1)
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            hold_days = sell_idx - buy_idx
            
            results.append({
                'return': ret,
                'hold_days': hold_days,
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
            
            avg_hold = np.mean(df['hold_days'].to_numpy())
            
            print(f"{trailing_pct:>7.1f}% {n:>8} {win_rate:>7.1f}% {avg_ret:>+9.2f}% {pf:>8.2f} {avg_hold:>7.1f}天")
    
    print("\n" + "="*70)
    print("【不同反弹类型的最佳卖点】")
    print("="*70)
    
    for rebound_type, trades_subset in [("小反弹(≤3%)", small_rebound), 
                                         ("中反弹(3-8%)", medium_rebound), 
                                         ("大反弹(>8%)", large_rebound)]:
        print(f"\n{rebound_type}:")
        
        best_result = None
        best_trailing = 0
        
        for trailing_pct in [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
            results = []
            
            for t in trades_subset:
                buy_idx = None
                stock_data = data.daily_data[t['stock_code']]
                dates = stock_data['dates']
                close = stock_data['close']
                high = stock_data['high']
                
                for idx, d in enumerate(dates):
                    if d == t['buy_date']:
                        buy_idx = idx
                        break
                
                if buy_idx is None:
                    continue
                
                buy_price = close[buy_idx]
                highest_price = buy_price
                sell_idx = None
                
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
                        break
                
                if sell_idx is None:
                    sell_idx = min(buy_idx + 20, len(close) - 1)
                
                sell_price = close[sell_idx]
                ret = (sell_price - buy_price) / buy_price * 100
                
                results.append(ret)
            
            if results:
                returns = np.array(results)
                avg_ret = np.mean(returns)
                
                if best_result is None or avg_ret > best_result:
                    best_result = avg_ret
                    best_trailing = trailing_pct
        
        if best_result is not None:
            print(f"  最佳回撤: {best_trailing}%, 平均收益: {best_result:+.2f}%")


if __name__ == "__main__":
    analyze_rebound_patterns()
