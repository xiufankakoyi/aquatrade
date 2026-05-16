"""
在原有策略基础上逐个验证假设

原有策略：
- 买点：绿柱凹函数收缩（4根绿柱递增，且收缩加速）
- 卖点：红柱收缩卖出

改进假设（逐个验证）：
1. 只要主板票（60，00开头）
2. 在持仓期间如果绿柱反弹变长立刻卖出
3. MACD绿柱值 > -0.015 才买入（调参）
4. 从最高点回撤2-3%卖出
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


def run_backtest(
    data,
    date_industry_ranks: dict,
    main_board_only: bool = False,
    sell_on_green_expand: bool = False,
    min_histogram_value: float = -999,
    trailing_stop_pct: float = 0,
    max_hold_days: int = 20,
) -> dict:
    """
    运行回测
    
    参数:
    - main_board_only: 只选主板票（60，00开头）
    - sell_on_green_expand: 持仓期间绿柱变长立刻卖出
    - min_histogram_value: MACD绿柱值阈值，只有 > 这个值才买入
    - trailing_stop_pct: 回撤止盈百分比，0表示不启用
    """
    results = []
    
    for stock_code in data.stock_codes:
        if main_board_only:
            if not (stock_code.startswith('60') or stock_code.startswith('00')):
                continue
        
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
            
            if bars[3] <= min_histogram_value:
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
            if buy_idx >= len(close) - max_hold_days:
                continue
            
            buy_price = close[buy_idx]
            
            sell_idx = None
            hold_days = 0
            sell_reason = ""
            
            highest_price = buy_price
            
            for d in range(1, max_hold_days + 1):
                if buy_idx + d >= len(close):
                    break
                
                current_price = close[buy_idx + d]
                current_high = high[buy_idx + d]
                
                if current_high > highest_price:
                    highest_price = current_high
                
                if sell_on_green_expand:
                    if histogram[buy_idx + d] < 0 and d >= 1:
                        if histogram[buy_idx + d] < histogram[buy_idx + d - 1]:
                            sell_idx = buy_idx + d
                            hold_days = d
                            sell_reason = "绿柱变长"
                            break
                
                if histogram[buy_idx + d] > 0 and d >= 1:
                    if histogram[buy_idx + d] < histogram[buy_idx + d - 1]:
                        sell_idx = buy_idx + d
                        hold_days = d
                        sell_reason = "红柱收缩"
                        break
                
                if trailing_stop_pct > 0:
                    drawdown = (highest_price - current_price) / highest_price * 100
                    if drawdown >= trailing_stop_pct:
                        sell_idx = buy_idx + d
                        hold_days = d
                        sell_reason = "回撤止盈"
                        break
            
            if sell_idx is None:
                sell_idx = min(buy_idx + max_hold_days, len(close) - 1)
                hold_days = max_hold_days
                sell_reason = "超时"
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'hold_days': hold_days,
                'sell_reason': sell_reason,
            })
    
    if not results:
        return None
    
    df = pl.DataFrame(results)
    returns = df['return'].to_numpy()
    
    n = len(returns)
    win_count = np.sum(returns > 0)
    win_rate = win_count / n * 100
    
    total_profit = np.sum(returns[returns > 0])
    total_loss = np.abs(np.sum(returns[returns < 0]))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    return {
        'total_trades': n,
        'win_rate': win_rate,
        'avg_return': np.mean(returns),
        'median_return': np.median(returns),
        'profit_factor': profit_factor,
        'avg_hold_days': np.mean(df['hold_days'].to_numpy()),
    }


def main():
    print("\n" + "="*70)
    print("在原有策略基础上逐个验证改进假设")
    print("="*70)
    print("时间范围: 2024-2025")
    print("原有策略: 绿柱凹函数收缩买入 + 红柱收缩卖出")
    
    data = get_cache()
    date_industry_ranks = {}
    
    print("\n" + "="*100)
    print("【基准策略】原有策略，无改进")
    print("="*100)
    
    result = run_backtest(
        data, date_industry_ranks,
        main_board_only=False,
        sell_on_green_expand=False,
        min_histogram_value=-999,
        trailing_stop_pct=0,
    )
    
    if result:
        print(f"  总交易数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.1f}%")
        print(f"  平均收益: {result['avg_return']:+.2f}%")
        print(f"  盈利因子: {result['profit_factor']:.2f}")
    
    baseline_return = result['avg_return'] if result else 0
    baseline_pf = result['profit_factor'] if result else 0
    
    print("\n" + "="*100)
    print("【假设1】只要主板票（60，00开头）")
    print("="*100)
    
    date_industry_ranks = {}
    result = run_backtest(
        data, date_industry_ranks,
        main_board_only=True,
        sell_on_green_expand=False,
        min_histogram_value=-999,
        trailing_stop_pct=0,
    )
    
    if result:
        print(f"  总交易数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.1f}%")
        print(f"  平均收益: {result['avg_return']:+.2f}% (基准: {baseline_return:+.2f}%)")
        print(f"  盈利因子: {result['profit_factor']:.2f} (基准: {baseline_pf:.2f})")
    
    print("\n" + "="*100)
    print("【假设2】持仓期间绿柱变长立刻卖出")
    print("="*100)
    
    date_industry_ranks = {}
    result = run_backtest(
        data, date_industry_ranks,
        main_board_only=False,
        sell_on_green_expand=True,
        min_histogram_value=-999,
        trailing_stop_pct=0,
    )
    
    if result:
        print(f"  总交易数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.1f}%")
        print(f"  平均收益: {result['avg_return']:+.2f}% (基准: {baseline_return:+.2f}%)")
        print(f"  盈利因子: {result['profit_factor']:.2f} (基准: {baseline_pf:.2f})")
    
    print("\n" + "="*100)
    print("【假设3】MACD绿柱值阈值过滤")
    print("="*100)
    
    histogram_thresholds = [-0.025, -0.020, -0.015, -0.010, -0.005]
    
    print(f"\n{'MACD阈值':>12} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*60)
    
    for thresh in histogram_thresholds:
        date_industry_ranks = {}
        result = run_backtest(
            data, date_industry_ranks,
            main_board_only=False,
            sell_on_green_expand=False,
            min_histogram_value=thresh,
            trailing_stop_pct=0,
        )
        
        if result:
            print(f"{thresh:>+10.3f} {result['total_trades']:>8} {result['win_rate']:>7.1f}% "
                  f"{result['avg_return']:>+9.2f}% {result['profit_factor']:>8.2f}")
    
    print("\n" + "="*100)
    print("【假设4】回撤止盈")
    print("="*100)
    
    trailing_stops = [2.0, 3.0, 4.0, 5.0]
    
    print(f"\n{'回撤%':>8} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*60)
    
    for pct in trailing_stops:
        date_industry_ranks = {}
        result = run_backtest(
            data, date_industry_ranks,
            main_board_only=False,
            sell_on_green_expand=False,
            min_histogram_value=-999,
            trailing_stop_pct=pct,
        )
        
        if result:
            print(f"{pct:>7.1f}% {result['total_trades']:>8} {result['win_rate']:>7.1f}% "
                  f"{result['avg_return']:>+9.2f}% {result['profit_factor']:>8.2f}")
    
    print("\n" + "="*100)
    print("【组合测试】最佳参数组合")
    print("="*100)
    
    print(f"\n{'主板':>6} {'绿柱变长':>8} {'MACD阈值':>10} {'回撤%':>8} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*90)
    
    best_results = []
    
    for main_board in [True, False]:
        for green_expand in [True, False]:
            for thresh in [-0.015, -0.010, -0.005]:
                for pct in [3.0, 4.0, 5.0]:
                    date_industry_ranks = {}
                    result = run_backtest(
                        data, date_industry_ranks,
                        main_board_only=main_board,
                        sell_on_green_expand=green_expand,
                        min_histogram_value=thresh,
                        trailing_stop_pct=pct,
                    )
                    
                    if result:
                        best_results.append({
                            'main_board': main_board,
                            'green_expand': green_expand,
                            'thresh': thresh,
                            'pct': pct,
                            **result
                        })
                        
                        print(f"{'✓' if main_board else '✗':>6} "
                              f"{'✓' if green_expand else '✗':>8} "
                              f"{thresh:>+10.3f} {pct:>7.1f}% "
                              f"{result['total_trades']:>8} {result['win_rate']:>7.1f}% "
                              f"{result['avg_return']:>+9.2f}% {result['profit_factor']:>8.2f}")
    
    print("\n" + "="*100)
    print("【最佳组合 Top 5】")
    print("="*100)
    
    sorted_by_return = sorted(best_results, key=lambda x: x['avg_return'], reverse=True)
    
    for i, r in enumerate(sorted_by_return[:5], 1):
        print(f"\n{i}. 主板={'✓' if r['main_board'] else '✗'}, 绿柱变长卖={'✓' if r['green_expand'] else '✗'}, "
              f"MACD阈值={r['thresh']}, 回撤={r['pct']}%")
        print(f"   平均收益 {r['avg_return']:+.2f}%, 胜率 {r['win_rate']:.1f}%, 盈利因子 {r['profit_factor']:.2f}")


if __name__ == "__main__":
    main()
