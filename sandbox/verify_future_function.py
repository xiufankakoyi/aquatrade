"""
验证数据是否存在未来函数问题

检查点：
1. 买入价格是否正确（应该用次日开盘价，不是收盘价）
2. 卖出价格是否正确
3. 信号检测是否使用了未来数据
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


def verify_trades():
    print("\n" + "="*70)
    print("验证交易数据 - 检查未来函数问题")
    print("="*70)
    
    data = get_cache()
    
    date_industry_ranks = {}
    trades = []
    
    for stock_code in data.stock_codes[:100]:
        stock_data = data.daily_data[stock_code]
        close = stock_data['close']
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
            
            trade_date = dates[i]
            
            cache_key = (trade_date, industry)
            if cache_key not in date_industry_ranks:
                date_industry_ranks[cache_key] = calculate_stock_rank_on_date(data, trade_date, industry)
            
            rank_dict = date_industry_ranks[cache_key]
            stock_rank = rank_dict.get(stock_code, 0)
            
            if stock_rank < 80:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - 3:
                continue
            
            sell_idx = None
            for j in range(buy_idx + 1, min(buy_idx + 21, len(histogram))):
                if histogram[j] > 0:
                    sell_idx = j
                    break
            
            if sell_idx is None:
                sell_idx = min(buy_idx + 20, len(close) - 1)
            
            buy_price_close = close[buy_idx]
            buy_price_open = open_price[buy_idx]
            sell_price_close = close[sell_idx]
            sell_price_open = open_price[sell_idx]
            
            ret_close = (sell_price_close - buy_price_close) / buy_price_close * 100
            ret_open = (sell_price_close - buy_price_open) / buy_price_open * 100
            
            trades.append({
                'stock_code': stock_code,
                'signal_date': dates[i],
                'buy_date': dates[buy_idx],
                'sell_date': dates[sell_idx],
                'buy_price_close': buy_price_close,
                'buy_price_open': buy_price_open,
                'sell_price_close': sell_price_close,
                'ret_close': ret_close,
                'ret_open': ret_open,
                'hold_days': sell_idx - buy_idx,
                'histogram_signal': histogram[i],
                'histogram_buy': histogram[buy_idx],
                'histogram_sell': histogram[sell_idx] if sell_idx < len(histogram) else 0,
            })
    
    if not trades:
        print("没有找到交易记录")
        return
    
    df = pl.DataFrame(trades)
    
    print(f"\n共找到 {len(df)} 笔交易")
    
    print("\n" + "="*100)
    print("【问题1: 买入价格检查】")
    print("="*100)
    print("如果用收盘价买入（错误），收益会偏高")
    print("正确做法：信号日收盘确认信号 → 次日开盘买入")
    
    avg_ret_close = df['ret_close'].mean()
    avg_ret_open = df['ret_open'].mean()
    
    print(f"\n用收盘价买入的平均收益: {avg_ret_close:.2f}%")
    print(f"用开盘价买入的平均收益: {avg_ret_open:.2f}%")
    print(f"差异: {avg_ret_close - avg_ret_open:.2f}%")
    
    print("\n" + "="*100)
    print("【问题2: 检查是否使用了未来数据】")
    print("="*100)
    
    print("\n前10笔交易详情:")
    print("-"*100)
    
    for row in df.head(10).iter_rows(named=True):
        print(f"\n股票: {row['stock_code']}")
        print(f"  信号日: {row['signal_date']}, histogram={row['histogram_signal']:.4f}")
        print(f"  买入日: {row['buy_date']}, 开盘价={row['buy_price_open']:.2f}, 收盘价={row['buy_price_close']:.2f}")
        print(f"  卖出日: {row['sell_date']}, 收盘价={row['sell_price_close']:.2f}, histogram={row['histogram_sell']:.4f}")
        print(f"  持仓天数: {row['hold_days']}")
        print(f"  收益(收盘买): {row['ret_close']:.2f}%")
        print(f"  收益(开盘买): {row['ret_open']:.2f}%")
    
    print("\n" + "="*100)
    print("【问题3: 检查卖出时机】")
    print("="*100)
    
    sell_on_red = df.filter(pl.col('histogram_sell') > 0)
    sell_on_green = df.filter(pl.col('histogram_sell') <= 0)
    
    print(f"\n在红柱日卖出的交易: {len(sell_on_red)} 笔")
    print(f"  平均收益(收盘买): {sell_on_red['ret_close'].mean():.2f}%")
    print(f"  平均收益(开盘买): {sell_on_red['ret_open'].mean():.2f}%")
    
    print(f"\n在绿柱日卖出的交易(超时): {len(sell_on_green)} 笔")
    print(f"  平均收益(收盘买): {sell_on_green['ret_close'].mean():.2f}%")
    print(f"  平均收益(开盘买): {sell_on_green['ret_open'].mean():.2f}%")
    
    print("\n" + "="*100)
    print("【问题4: 检查极端收益】")
    print("="*100)
    
    sorted_df = df.sort('ret_close', descending=True)
    
    print("\n收益最高的5笔交易:")
    for row in sorted_df.head(5).iter_rows(named=True):
        print(f"  {row['stock_code']}: {row['ret_close']:.2f}% (持仓{row['hold_days']}天)")
    
    print("\n收益最低的5笔交易:")
    for row in sorted_df.tail(5).iter_rows(named=True):
        print(f"  {row['stock_code']}: {row['ret_close']:.2f}% (持仓{row['hold_days']}天)")
    
    print("\n" + "="*100)
    print("【结论】")
    print("="*100)
    
    if abs(avg_ret_close - avg_ret_open) > 1:
        print(f"\n⚠️  警告: 用收盘价买入和用开盘价买入差异较大 ({avg_ret_close - avg_ret_open:.2f}%)")
        print("   可能存在未来函数问题！")
        print("   正确做法应该用次日开盘价买入")
    else:
        print("\n✅ 买入价格差异较小，数据可能正确")


if __name__ == "__main__":
    verify_trades()
