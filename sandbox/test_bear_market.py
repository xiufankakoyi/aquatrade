"""
熊市期间策略对比测试

时间范围：2023.5.4 - 2024.9.24（熊市）
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict

from config.logger import get_logger

logger = get_logger(__name__)


def calculate_macd_numba(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    n = len(close)
    histogram = np.empty(n, dtype=np.float64)
    
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    alpha_signal = 2.0 / (signal + 1)
    
    ema_fast = close[0]
    ema_slow = close[0]
    dea = 0.0
    
    for i in range(n):
        ema_fast = alpha_fast * close[i] + (1 - alpha_fast) * ema_fast
        ema_slow = alpha_slow * close[i] + (1 - alpha_slow) * ema_slow
        dif = ema_fast - ema_slow
        dea = alpha_signal * dif + (1 - alpha_signal) * dea
        histogram[i] = (dif - dea) * 2
    
    return histogram


def calculate_volume_ma_numba(volume: np.ndarray, period: int = 5):
    n = len(volume)
    result = np.empty(n, dtype=np.float64)
    
    cumsum = 0.0
    for i in range(n):
        cumsum += volume[i]
        if i >= period:
            cumsum -= volume[i - period]
        result[i] = cumsum / min(i + 1, period)
    
    return result


def calculate_stock_rank_on_date(daily_data, trade_date: str, industry_stocks: list) -> Dict[str, float]:
    stocks_in_industry = []
    
    for stock_code in industry_stocks:
        stock_data = daily_data.get(stock_code)
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


def load_data(start_date: str, end_date: str):
    print("\n" + "="*60)
    print(f"加载数据: {start_date} - {end_date}")
    print("="*60)
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print("\n[1/3] 加载股票信息...")
    table = db.open_table("stock_info")
    stock_info_df = pl.from_arrow(table.to_arrow())
    
    stock_info = {}
    industry_stocks = {}
    for row in stock_info_df.iter_rows(named=True):
        stock_info[row['stock_code']] = {
            'name': row.get('stock_name', ''),
            'industry': row.get('industry'),
        }
        industry = row.get('industry')
        if industry:
            if industry not in industry_stocks:
                industry_stocks[industry] = []
            industry_stocks[industry].append(row['stock_code'])
    
    print(f"  股票信息: {len(stock_info)} 只")
    
    print("\n[2/3] 加载日线数据...")
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_df = daily_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        stock_code = row['stock_code']
        if stock_code not in daily_data:
            daily_data[stock_code] = {
                'dates': [],
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
            }
        daily_data[stock_code]['dates'].append(str(row['trade_date']))
        daily_data[stock_code]['open'].append(row.get('open', row.get('close')))
        daily_data[stock_code]['high'].append(row.get('high', row.get('close')))
        daily_data[stock_code]['low'].append(row.get('low', row.get('close')))
        daily_data[stock_code]['close'].append(row['close'])
        daily_data[stock_code]['volume'].append(row['volume'])
    
    for stock_code in daily_data:
        dates_arr = np.array(daily_data[stock_code]['dates'])
        sorted_idx = np.argsort(dates_arr)
        
        for key in ['dates', 'open', 'high', 'low', 'close', 'volume']:
            arr = np.array(daily_data[stock_code][key])
            daily_data[stock_code][key] = arr[sorted_idx]
    
    print(f"  日线数据: {len(daily_data)} 只股票")
    
    return stock_info, daily_data, industry_stocks


def run_backtest(daily_data, stock_info, industry_stocks, strategy: str):
    results = []
    strength_results = {'weak': [], 'medium': [], 'strong': []}
    date_industry_ranks = {}
    
    for stock_code in daily_data:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
        low = stock_data['low']
        volume = stock_data['volume']
        dates = stock_data['dates']
        
        if len(close) < 50:
            continue
        
        info = stock_info.get(stock_code, {})
        industry = info.get('industry')
        if not industry:
            continue
        
        histogram = calculate_macd_numba(close)
        volume_ma5 = calculate_volume_ma_numba(volume)
        
        for i in range(4, len(histogram) - 20):
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
            
            if bars[3] > -0.005:
                continue
            
            vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
            if vol_ratio < 1.5:
                continue
            
            trade_date = dates[i]
            
            cache_key = (trade_date, industry)
            if cache_key not in date_industry_ranks:
                industry_stock_list = industry_stocks.get(industry, [])
                date_industry_ranks[cache_key] = calculate_stock_rank_on_date(
                    daily_data, trade_date, industry_stock_list
                )
            
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
            
            sell_idx = None
            hold_days = 0
            
            if strategy == 'fixed_5pct':
                highest_price = buy_price
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
                        hold_days = d
                        break
                if sell_idx is None:
                    sell_idx = min(buy_idx + 20, len(close) - 1)
                    hold_days = sell_idx - buy_idx
            
            elif strategy == 'dynamic':
                if day1_high_ret < 1:
                    trailing_pct = 2.0
                    stop_loss_pct = 3.0
                elif day1_high_ret < 3:
                    trailing_pct = 5.0
                    stop_loss_pct = 5.0
                else:
                    trailing_pct = 8.0
                    stop_loss_pct = 8.0
                
                highest_price = buy_price
                for d in range(1, 11):
                    if buy_idx + d >= len(close):
                        break
                    current_price = close[buy_idx + d]
                    current_high = high[buy_idx + d]
                    if current_high > highest_price:
                        highest_price = current_high
                    max_profit = (highest_price - buy_price) / buy_price * 100
                    current_loss = (buy_price - current_price) / buy_price * 100
                    if max_profit <= 0 and current_loss >= stop_loss_pct:
                        sell_idx = buy_idx + d
                        hold_days = d
                        break
                    if max_profit > 0:
                        drawdown = (highest_price - current_price) / highest_price * 100
                        if drawdown >= trailing_pct:
                            sell_idx = buy_idx + d
                            hold_days = d
                            break
                if sell_idx is None:
                    sell_idx = min(buy_idx + 10, len(close) - 1)
                    hold_days = sell_idx - buy_idx
            
            elif strategy == 'strong_only':
                if day1_high_ret < 3:
                    continue
                highest_price = buy_price
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
                        hold_days = d
                        break
                if sell_idx is None:
                    sell_idx = min(buy_idx + 20, len(close) - 1)
                    hold_days = sell_idx - buy_idx
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'hold_days': hold_days,
                'day1_high_ret': day1_high_ret,
            })
            
            if day1_high_ret < 1:
                strength_results['weak'].append(ret)
            elif day1_high_ret < 3:
                strength_results['medium'].append(ret)
            else:
                strength_results['strong'].append(ret)
    
    return results, strength_results


def main():
    print("\n" + "="*70)
    print("熊市期间策略对比测试")
    print("="*70)
    print("时间范围: 2023.5.4 - 2024.9.24")
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    strategies = [
        ('fixed_5pct', '固定5%止盈'),
        ('dynamic', '动态回撤止盈'),
        ('strong_only', '只做强势(第1天>=3%)'),
    ]
    
    print(f"\n{'策略':>25} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*60)
    
    for strategy_key, strategy_name in strategies:
        results, _ = run_backtest(daily_data, stock_info, industry_stocks, strategy_key)
        
        if results:
            returns = np.array([r['return'] for r in results])
            n = len(returns)
            win_rate = np.sum(returns > 0) / n * 100
            avg_ret = np.mean(returns)
            
            total_profit = np.sum(returns[returns > 0])
            total_loss = np.abs(np.sum(returns[returns < 0]))
            pf = total_profit / total_loss if total_loss > 0 else float('inf')
            
            print(f"{strategy_name:>25} {n:>8} {win_rate:>7.1f}% {avg_ret:>+9.2f}% {pf:>8.2f}")
    
    print("\n" + "="*70)
    print("【各强度类型在熊市的表现】")
    print("="*70)
    
    results, strength_results = run_backtest(daily_data, stock_info, industry_stocks, 'fixed_5pct')
    
    for strength, type_name in [('weak', '弱势(<1%)'), ('medium', '中势(1-3%)'), ('strong', '强势(>=3%)')]:
        type_ret = strength_results[strength]
        if type_ret:
            arr = np.array(type_ret)
            print(f"\n{type_name}:")
            print(f"  数量: {len(arr)}")
            print(f"  平均收益: {np.mean(arr):+.2f}%")
            print(f"  胜率: {np.sum(arr > 0) / len(arr) * 100:.1f}%")


if __name__ == "__main__":
    main()
