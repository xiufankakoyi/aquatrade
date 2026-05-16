"""
测试三个筛选条件对弱反弹的过滤效果

条件1: 板块指数在20日均线之上(板块处于上升趋势)
条件2: 板块内涨停个股 >3只 或 板块涨幅 >2%(有资金活跃)
条件3: 个股是板块内形态最强的几只之一(涨幅排名前20%)
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

from sandbox.data_cache import get_cache, calculate_macd_numba, calculate_volume_ma_numba


def calculate_stock_rank_on_date(
    data,
    trade_date: str,
    industry: str,
) -> Dict[str, float]:
    """
    计算某日某板块内所有个股的涨幅排名
    
    Returns:
        {stock_code: rank_percentile} 排名百分位 (0-100, 越大越强)
    """
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


def test_filters(
    use_filter_1: bool = False,
    use_filter_2: bool = False,
    use_filter_3: bool = False,
    filter_3_top_pct: float = 20.0,
    filter_name: str = "",
):
    """测试筛选条件"""
    data = get_cache()
    
    date_industry_ranks = {}
    results = []
    total_signals = 0
    filtered_by_1 = 0
    filtered_by_2 = 0
    filtered_by_3 = 0
    
    for stock_code in data.stock_codes:
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
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
        
        for i in range(4, len(histogram) - 10):
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
            
            total_signals += 1
            trade_date = dates[i]
            
            sector_info = data.sector_data.get(trade_date, {}).get(industry, {})
            
            if use_filter_1:
                sector_index = sector_info.get('sector_index', 0)
                ma20 = sector_info.get('ma20', None)
                if ma20 is None or sector_index < ma20:
                    filtered_by_1 += 1
                    continue
            
            if use_filter_2:
                limit_up = sector_info.get('limit_up_count', 0)
                pct_chg = sector_info.get('pct_chg', 0)
                if limit_up <= 3 and pct_chg <= 2:
                    filtered_by_2 += 1
                    continue
            
            if use_filter_3:
                cache_key = (trade_date, industry)
                if cache_key not in date_industry_ranks:
                    date_industry_ranks[cache_key] = calculate_stock_rank_on_date(data, trade_date, industry)
                
                rank_dict = date_industry_ranks[cache_key]
                stock_rank = rank_dict.get(stock_code, 0)
                
                if stock_rank < (100 - filter_3_top_pct):
                    filtered_by_3 += 1
                    continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - 3:
                continue
            
            buy_price = close[buy_idx]
            
            sell_day = None
            for j in range(buy_idx + 1, min(buy_idx + 4, len(histogram))):
                if histogram[j] > 0 and histogram[j] < histogram[j - 1]:
                    sell_day = j - buy_idx
                    break
            
            ret_3d = (close[buy_idx + 3] - buy_price) / buy_price * 100 if buy_idx + 3 < len(close) else None
            
            results.append({
                'sell_in_3d': sell_day is not None and sell_day <= 3,
                'ret_3d': ret_3d,
            })
    
    if not results:
        return None
    
    df = pl.DataFrame(results)
    n = len(df)
    
    weak_signals = df.filter(pl.col('sell_in_3d') == True)
    strong_signals = df.filter(pl.col('sell_in_3d') == False)
    
    weak_ratio = len(weak_signals) / n * 100 if n > 0 else 0
    weak_ret = np.mean(weak_signals['ret_3d'].drop_nulls().to_numpy()) if len(weak_signals) > 0 else 0
    strong_ret = np.mean(strong_signals['ret_3d'].drop_nulls().to_numpy()) if len(strong_signals) > 0 else 0
    total_ret = np.mean(df['ret_3d'].drop_nulls().to_numpy()) if n > 0 else 0
    
    return {
        'filter_name': filter_name,
        'total_signals': total_signals,
        'passed_signals': n,
        'filtered_by_1': filtered_by_1,
        'filtered_by_2': filtered_by_2,
        'filtered_by_3': filtered_by_3,
        'weak_count': len(weak_signals),
        'strong_count': len(strong_signals),
        'weak_ratio': weak_ratio,
        'weak_ret': weak_ret,
        'strong_ret': strong_ret,
        'total_ret': total_ret,
    }


def main():
    print("\n" + "="*70)
    print("筛选条件测试 (含条件3)")
    print("="*70)
    
    print("\n预加载数据...")
    get_cache()
    
    tests = [
        (False, False, False, 20, "无筛选(基准)"),
        (True, False, False, 20, "条件1: 板块在MA20之上"),
        (False, True, False, 20, "条件2: 涨停>3或涨幅>2%"),
        (False, False, True, 20, "条件3: 板块内涨幅前20%"),
        (False, False, True, 30, "条件3: 板块内涨幅前30%"),
        (False, False, True, 50, "条件3: 板块内涨幅前50%"),
        (True, True, False, 20, "条件1+2"),
        (True, True, True, 20, "条件1+2+3"),
        (False, True, True, 20, "条件2+3"),
    ]
    
    print("\n" + "="*70)
    print("测试结果")
    print("="*70)
    
    print(f"""
{'筛选条件':<30} {'信号数':>6} {'弱反弹':>6} {'弱反弹比':>8} {'弱反弹收益':>10} {'强反弹收益':>10} {'总收益':>8}
{'-'*78}""")
    
    baseline = None
    for use_1, use_2, use_3, top_pct, name in tests:
        result = test_filters(use_1, use_2, use_3, top_pct, name)
        if result:
            if baseline is None:
                baseline = result
            print(f"{result['filter_name']:<30} {result['passed_signals']:>6} {result['weak_count']:>6} "
                  f"{result['weak_ratio']:>7.1f}% {result['weak_ret']:>9.2f}% {result['strong_ret']:>9.2f}% "
                  f"{result['total_ret']:>7.2f}%")
    
    print(f"\n{'='*70}")
    print("分析")
    print("="*70)
    
    if baseline:
        print(f"""
【基准数据】
  总信号数: {baseline['passed_signals']}
  弱反弹比例: {baseline['weak_ratio']:.1f}%
  弱反弹收益: {baseline['weak_ret']:.2f}%
  强反弹收益: {baseline['strong_ret']:.2f}%
  总收益: {baseline['total_ret']:.2f}%
""")
    
    print("【各条件效果对比】\n")
    
    for use_1, use_2, use_3, top_pct, name in tests[1:]:
        result = test_filters(use_1, use_2, use_3, top_pct, name)
        if result and baseline:
            weak_reduction = baseline['weak_ratio'] - result['weak_ratio']
            ret_improvement = result['total_ret'] - baseline['total_ret']
            signal_reduction = baseline['passed_signals'] - result['passed_signals']
            
            weak_status = "✅" if weak_reduction > 0 else "❌"
            ret_status = "✅" if ret_improvement > 0 else "❌"
            
            print(f"【{name}】")
            print(f"  过滤信号: {signal_reduction} 个")
            print(f"  {weak_status} 弱反弹变化: {weak_reduction:+.1f} 个百分点")
            print(f"  {ret_status} 总收益变化: {ret_improvement:+.2f}%")
            print()


if __name__ == "__main__":
    main()
