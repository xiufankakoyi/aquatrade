"""
跟随强势策略

核心思路：
- T日：信号日
- T+1日：观察日（不买入）
- T+2日：如果盘中强势（涨幅>=3%），则追入

问题：追入价格不确定，可能错过最佳买点
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


def run_backtest_follow_strength(daily_data, stock_info, industry_stocks, 
                                  strength_threshold: float = 3.0,
                                  buy_at: str = 'open'):
    """
    跟随强势策略
    
    Args:
        strength_threshold: 强势阈值（最高涨幅）
        buy_at: 买入时机
            - 'open': T+2日开盘买入（如果T+1日强势）
            - 'strength': T+2日涨幅达到阈值时买入（模拟）
            - 'next_open': T+3日开盘买入（如果T+2日强势）
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
        
        for i in range(4, len(histogram) - 25):
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
            
            if t3_idx >= len(close) - 20:
                continue
            
            t0_close = close[t0_idx]
            
            if buy_at == 'open':
                t1_high = high[t1_idx]
                t1_high_ret = (t1_high - t0_close) / t0_close * 100
                
                if t1_high_ret < strength_threshold:
                    continue
                
                buy_idx = t2_idx
                buy_price = open_price[t2_idx]
                
            elif buy_at == 'strength':
                t1_high = high[t1_idx]
                t1_high_ret = (t1_high - t0_close) / t0_close * 100
                
                if t1_high_ret < strength_threshold:
                    continue
                
                buy_idx = t2_idx
                buy_price = open_price[t2_idx] * (1 + strength_threshold / 100)
                
            elif buy_at == 'next_open':
                t2_high = high[t2_idx]
                t2_open = open_price[t2_idx]
                t2_high_ret = (t2_high - t2_open) / t2_open * 100
                
                if t2_high_ret < strength_threshold:
                    continue
                
                buy_idx = t3_idx
                buy_price = open_price[t3_idx]
            
            else:
                continue
            
            if buy_idx >= len(close) - 20:
                continue
            
            day1_high = high[buy_idx] if buy_idx < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
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
            
            results.append({
                'return': ret,
                'day1_high_ret': day1_high_ret,
            })
    
    return results


def run_backtest_partial_position(daily_data, stock_info, industry_stocks,
                                   first_position: float = 0.5,
                                   strength_threshold: float = 3.0):
    """
    分批建仓策略
    
    Args:
        first_position: 首次建仓比例
        strength_threshold: 加仓阈值
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
        
        for i in range(4, len(histogram) - 25):
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
            
            if t2_idx >= len(close) - 20:
                continue
            
            t0_close = close[t0_idx]
            t1_close = close[t1_idx]
            t1_high = high[t1_idx]
            
            buy_price_1 = t1_close
            position_1 = first_position
            
            t1_high_ret = (t1_high - t0_close) / t0_close * 100
            
            if t1_high_ret >= strength_threshold:
                t2_open = open_price[t2_idx]
                buy_price_2 = t2_open
                position_2 = 1 - first_position
            else:
                buy_price_2 = None
                position_2 = 0
            
            highest_price = buy_price_1
            sell_idx = None
            
            for d in range(1, 21):
                if t1_idx + d >= len(close):
                    break
                
                current_price = close[t1_idx + d]
                current_high = high[t1_idx + d]
                
                if current_high > highest_price:
                    highest_price = current_high
                
                drawdown = (highest_price - current_price) / highest_price * 100
                if drawdown >= 5:
                    sell_idx = t1_idx + d
                    break
            
            if sell_idx is None:
                sell_idx = min(t1_idx + 20, len(close) - 1)
            
            sell_price = close[sell_idx]
            
            ret_1 = (sell_price - buy_price_1) / buy_price_1 * 100
            
            if buy_price_2:
                ret_2 = (sell_price - buy_price_2) / buy_price_2 * 100
                weighted_ret = ret_1 * position_1 + ret_2 * position_2
            else:
                weighted_ret = ret_1
            
            results.append({
                'return': weighted_ret,
                'day1_high_ret': t1_high_ret,
                'added_position': buy_price_2 is not None,
            })
    
    return results


def main():
    print("\n" + "="*70)
    print("跟随强势策略测试")
    print("="*70)
    print("时间范围: 2023.5.4 - 2024.9.24 (熊市)")
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    print("\n" + "="*70)
    print("【跟随强势策略】")
    print("="*70)
    
    print("\n方案1: T+1日强势后，T+2日开盘买入")
    for threshold in [2.0, 3.0, 4.0, 5.0]:
        results = run_backtest_follow_strength(
            daily_data, stock_info, industry_stocks,
            strength_threshold=threshold,
            buy_at='open'
        )
        if results:
            returns = np.array([r['return'] for r in results])
            print(f"  阈值{threshold}%: 交易数{len(returns)}, 胜率{np.sum(returns > 0) / len(returns) * 100:.1f}%, 平均收益{np.mean(returns):+.2f}%")
    
    print("\n方案2: T+2日强势后，T+3日开盘买入")
    for threshold in [2.0, 3.0, 4.0, 5.0]:
        results = run_backtest_follow_strength(
            daily_data, stock_info, industry_stocks,
            strength_threshold=threshold,
            buy_at='next_open'
        )
        if results:
            returns = np.array([r['return'] for r in results])
            print(f"  阈值{threshold}%: 交易数{len(returns)}, 胜率{np.sum(returns > 0) / len(returns) * 100:.1f}%, 平均收益{np.mean(returns):+.2f}%")
    
    print("\n" + "="*70)
    print("【分批建仓策略】")
    print("="*70)
    
    for first_pos in [0.3, 0.5, 0.7]:
        results = run_backtest_partial_position(
            daily_data, stock_info, industry_stocks,
            first_position=first_pos,
            strength_threshold=3.0
        )
        if results:
            returns = np.array([r['return'] for r in results])
            added = sum(1 for r in results if r['added_position'])
            print(f"\n  首次仓位{first_pos*100:.0f}%:")
            print(f"    总交易数: {len(returns)}")
            print(f"    加仓次数: {added} ({added/len(returns)*100:.1f}%)")
            print(f"    胜率: {np.sum(returns > 0) / len(returns) * 100:.1f}%")
            print(f"    平均收益: {np.mean(returns):+.2f}%")
    
    print("\n" + "="*70)
    print("【结论】")
    print("="*70)
    print("""
核心问题：买入时无法预判第1天是否强势

可行方案：
1. 分批建仓：T+1日买入50%，T+2日强势确认后加仓50%
   - 优点：不错过强势机会，控制风险
   - 缺点：弱势时仍有损失

2. 跟随强势：T+2日强势确认后追入
   - 优点：只做强势，胜率高
   - 缺点：错过最佳买点，收益可能降低

3. 接受不确定性，优化止损：
   - 设置更严格的止损（如-3%）
   - 强势时放宽止盈（如回撤8%）
""")


if __name__ == "__main__":
    main()
