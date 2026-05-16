"""
优化后的跟随强势策略

发现：T+2日强势确认后，T+3日开盘买入效果最好

本脚本深入分析这个策略
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict

from config.logger import get_logger

logger = get_logger(__name__)


def calculate_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
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


def calculate_volume_ma(volume: np.ndarray, period: int = 5):
    n = len(volume)
    result = np.empty(n, dtype=np.float64)
    
    cumsum = 0.0
    for i in range(n):
        cumsum += volume[i]
        if i >= period:
            cumsum -= volume[i - period]
        result[i] = cumsum / min(i + 1, period)
    
    return result


def calculate_stock_rank(daily_data: dict, trade_date: str, industry_stocks: list) -> Dict[str, float]:
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


def run_backtest_follow_strength_v2(daily_data, stock_info, industry_stocks,
                                     strength_threshold: float = 3.0,
                                     trailing_pct: float = 5.0,
                                     max_hold_days: int = 20):
    """
    跟随强势策略 V2
    
    时间线：
    - T日：信号日
    - T+1日：观察日
    - T+2日：强势确认日（最高涨幅>=阈值）
    - T+3日：开盘买入
    """
    results = []
    date_industry_ranks = {}
    
    for stock_code in daily_data:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
        open_price = stock_data['open']
        volume = stock_data['volume']
        dates = stock_data['dates']
        
        if len(close) < 50:
            continue
        
        info = stock_info.get(stock_code, {})
        industry = info.get('industry')
        if not industry:
            continue
        
        histogram = calculate_macd(close)
        volume_ma5 = calculate_volume_ma(volume)
        
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
            
            if bars[3] > -0.005:
                continue
            
            vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
            if vol_ratio < 1.5:
                continue
            
            trade_date = dates[i]
            
            cache_key = (trade_date, industry)
            if cache_key not in date_industry_ranks:
                industry_stock_list = industry_stocks.get(industry, [])
                date_industry_ranks[cache_key] = calculate_stock_rank(
                    daily_data, trade_date, industry_stock_list
                )
            
            rank_dict = date_industry_ranks[cache_key]
            stock_rank = rank_dict.get(stock_code, 0)
            
            if stock_rank < 80:
                continue
            
            t0_idx = i
            t1_idx = i + 1
            t2_idx = i + 2
            t3_idx = i + 3
            
            if t3_idx >= len(close) - max_hold_days:
                continue
            
            t2_open = open_price[t2_idx]
            t2_high = high[t2_idx]
            t2_high_ret = (t2_high - t2_open) / t2_open * 100
            
            if t2_high_ret < strength_threshold:
                continue
            
            buy_idx = t3_idx
            buy_price = open_price[t3_idx]
            
            highest_price = buy_price
            sell_idx = None
            hold_days = 0
            
            for d in range(1, max_hold_days + 1):
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
                sell_idx = min(buy_idx + max_hold_days, len(close) - 1)
                hold_days = sell_idx - buy_idx
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'stock_code': stock_code,
                'buy_date': dates[buy_idx],
                'sell_date': dates[sell_idx],
                'buy_price': buy_price,
                'sell_price': sell_price,
                'return': ret,
                'hold_days': hold_days,
                't2_high_ret': t2_high_ret,
            })
    
    return results


def main():
    print("\n" + "="*70)
    print("优化后的跟随强势策略")
    print("="*70)
    print("时间范围: 2023.5.4 - 2024.9.24 (熊市)")
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    print("\n" + "="*70)
    print("【参数网格搜索】")
    print("="*70)
    
    strength_thresholds = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    trailing_pcts = [3.0, 4.0, 5.0, 6.0, 8.0]
    
    print(f"\n{'强势阈值':>8} {'回撤%':>6} {'交易数':>6} {'胜率':>6} {'平均收益':>8} {'盈利因子':>8}")
    print("-"*50)
    
    best_result = None
    best_params = None
    
    for strength in strength_thresholds:
        for trailing in trailing_pcts:
            results = run_backtest_follow_strength_v2(
                daily_data, stock_info, industry_stocks,
                strength_threshold=strength,
                trailing_pct=trailing
            )
            
            if not results:
                continue
            
            returns = np.array([r['return'] for r in results])
            n = len(returns)
            win_rate = np.sum(returns > 0) / n * 100
            avg_ret = np.mean(returns)
            
            total_profit = np.sum(returns[returns > 0])
            total_loss = np.abs(np.sum(returns[returns < 0]))
            pf = total_profit / total_loss if total_loss > 0 else float('inf')
            
            print(f"{strength:>7.1f}% {trailing:>5.0f}% {n:>6} {win_rate:>5.1f}% {avg_ret:>+7.2f}% {pf:>8.2f}")
            
            if best_result is None or avg_ret > best_result:
                best_result = avg_ret
                best_params = (strength, trailing, n, win_rate, pf)
    
    print("\n" + "="*70)
    print("【最优参数】")
    print("="*70)
    if best_params:
        print(f"  强势阈值: {best_params[0]}%")
        print(f"  回撤止盈: {best_params[1]}%")
        print(f"  交易数: {best_params[2]}")
        print(f"  胜率: {best_params[3]:.1f}%")
        print(f"  平均收益: {best_result:+.2f}%")
        print(f"  盈利因子: {best_params[4]:.2f}")
    
    print("\n" + "="*70)
    print("【策略总结】")
    print("="*70)
    print("""
时间线：
- T日：信号日（MACD绿柱收缩 + 板块排名前20% + 放量）
- T+1日：观察日（不操作）
- T+2日：强势确认日（盘中最高涨幅>=阈值）
- T+3日：开盘买入

优点：
1. 只做确认强势的股票
2. 避免了"买入时无法预判"的问题
3. 在熊市中表现优于原策略

缺点：
1. 错过了T+1、T+2日的涨幅
2. 交易机会减少
3. 可能追高买入
""")


if __name__ == "__main__":
    main()
