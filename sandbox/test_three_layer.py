"""
三层过滤策略测试

第1层：第1天最高涨幅 < 1% → 第2天开盘卖出
第2层：前2天最高涨幅 < 2% → 第3天开盘卖出
第3层：通过前两层 → 3%移动止盈，最长10天
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


def test_three_layer_strategy():
    print("\n" + "="*70)
    print("三层过滤策略测试")
    print("="*70)
    print("第1层：第1天最高涨幅 < 1% → 第2天开盘卖出")
    print("第2层：前2天最高涨幅 < 2% → 第3天开盘卖出")
    print("第3层：通过前两层 → 3%移动止盈，最长10天")
    
    data = get_cache()
    date_industry_ranks = {}
    
    results = []
    layer_results = {'layer1': [], 'layer2': [], 'layer3': []}
    
    for stock_code in data.stock_codes:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
        open_price = stock_data['open']
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
            if buy_idx >= len(close) - 15:
                continue
            
            buy_price = close[buy_idx]
            
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            day2_open = open_price[buy_idx + 2] if buy_idx + 2 < len(open_price) else close[buy_idx + 1]
            day2_high = high[buy_idx + 2] if buy_idx + 2 < len(high) else buy_price
            day2_high_ret = (day2_high - buy_price) / buy_price * 100
            
            day3_open = open_price[buy_idx + 3] if buy_idx + 3 < len(open_price) else close[buy_idx + 2]
            
            max_high_2d = max(day1_high_ret, day2_high_ret)
            
            sell_idx = None
            hold_days = 0
            exit_layer = ""
            
            if day1_high_ret < 1:
                exit_layer = "layer1"
                sell_idx = buy_idx + 2
                hold_days = 2
            elif max_high_2d < 2:
                exit_layer = "layer2"
                sell_idx = buy_idx + 3
                hold_days = 3
            else:
                exit_layer = "layer3"
                highest_price = buy_price
                
                for d in range(1, 11):
                    if buy_idx + d >= len(close):
                        break
                    
                    current_price = close[buy_idx + d]
                    current_high = high[buy_idx + d]
                    
                    if current_high > highest_price:
                        highest_price = current_high
                    
                    drawdown = (highest_price - current_price) / highest_price * 100
                    if drawdown >= 3:
                        sell_idx = buy_idx + d
                        hold_days = d
                        break
                
                if sell_idx is None:
                    sell_idx = min(buy_idx + 10, len(close) - 1)
                    hold_days = sell_idx - buy_idx
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'hold_days': hold_days,
                'exit_layer': exit_layer,
                'day1_high_ret': day1_high_ret,
                'max_high_2d': max_high_2d,
            })
            
            layer_results[exit_layer].append(ret)
    
    print(f"\n共 {len(results)} 笔交易")
    
    print("\n" + "="*70)
    print("【三层过滤结果】")
    print("="*70)
    
    returns = np.array([r['return'] for r in results])
    n = len(returns)
    win_rate = np.sum(returns > 0) / n * 100
    avg_ret = np.mean(returns)
    
    total_profit = np.sum(returns[returns > 0])
    total_loss = np.abs(np.sum(returns[returns < 0]))
    pf = total_profit / total_loss if total_loss > 0 else float('inf')
    
    print(f"  总交易数: {n}")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  平均收益: {avg_ret:+.2f}%")
    print(f"  盈利因子: {pf:.2f}")
    print(f"  平均持仓: {np.mean([r['hold_days'] for r in results]):.1f}天")
    
    print("\n" + "="*70)
    print("【各层分析】")
    print("="*70)
    
    for layer, layer_name in [('layer1', '第1层(第1天<1%)'), 
                               ('layer2', '第2层(前2天<2%)'), 
                               ('layer3', '第3层(通过过滤)')]:
        layer_ret = layer_results[layer]
        if layer_ret:
            arr = np.array(layer_ret)
            print(f"\n{layer_name}:")
            print(f"  数量: {len(arr)} ({len(arr)/n*100:.1f}%)")
            print(f"  平均收益: {np.mean(arr):+.2f}%")
            print(f"  胜率: {np.sum(arr > 0) / len(arr) * 100:.1f}%")
    
    print("\n" + "="*70)
    print("【验证：第3层是否成功过滤了小反弹？】")
    print("="*70)
    
    layer3_results = [r for r in results if r['exit_layer'] == 'layer3']
    
    if layer3_results:
        max_profit_3d_list = []
        for r in layer3_results:
            max_profit_3d_list.append(r['max_high_2d'])
        
        print(f"\n第3层交易的前2天最高涨幅分布:")
        arr = np.array(max_profit_3d_list)
        print(f"  平均: {np.mean(arr):.2f}%")
        print(f"  最小: {np.min(arr):.2f}%")
        print(f"  >2%比例: {np.sum(arr >= 2) / len(arr) * 100:.1f}%")
        print(f"  >3%比例: {np.sum(arr >= 3) / len(arr) * 100:.1f}%")
        print(f"  >5%比例: {np.sum(arr >= 5) / len(arr) * 100:.1f}%")
    
    print("\n" + "="*70)
    print("【对比基准策略】")
    print("="*70)
    
    print(f"\n{'策略':>25} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*60)
    
    print(f"{'三层过滤策略':>25} {n:>8} {win_rate:>7.1f}% {avg_ret:>+9.2f}% {pf:>8.2f}")
    
    date_industry_ranks = {}
    baseline_results = []
    
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
                if drawdown >= 5:
                    sell_idx = buy_idx + d
                    break
            
            if sell_idx is None:
                sell_idx = min(buy_idx + 20, len(close) - 1)
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            baseline_results.append(ret)
    
    if baseline_results:
        arr = np.array(baseline_results)
        baseline_win_rate = np.sum(arr > 0) / len(arr) * 100
        baseline_avg_ret = np.mean(arr)
        
        total_profit = np.sum(arr[arr > 0])
        total_loss = np.abs(np.sum(arr[arr < 0]))
        baseline_pf = total_profit / total_loss if total_loss > 0 else float('inf')
        
        print(f"{'基准(固定5%止盈)':>25} {len(arr):>8} {baseline_win_rate:>7.1f}% {baseline_avg_ret:>+9.2f}% {baseline_pf:>8.2f}")


if __name__ == "__main__":
    test_three_layer_strategy()
