"""
T+2日开盘确认策略

原策略问题：
- T日：信号日
- T+1日：收盘买入
- T+2日：观察是否强势（但买入时未知）

新策略：
- T日：信号日
- T+1日：观察日（不买入）
- T+2日：开盘确认强势后买入
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


def run_backtest_original(daily_data, stock_info, industry_stocks):
    """
    原策略：T+1日收盘买入
    """
    results = []
    date_industry_ranks = {}
    
    for stock_code in daily_data:
        if not (stock_code.startswith('60') or stock_code.startswith('00')):
            continue
        
        stock_data = daily_data[stock_code]
        close = stock_data['close']
        high = stock_data['high']
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
            
            t1_idx = i + 1
            if t1_idx >= len(close) - 20:
                continue
            
            buy_price = close[t1_idx]
            
            day1_high = high[t1_idx + 1] if t1_idx + 1 < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            highest_price = buy_price
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
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'day1_high_ret': day1_high_ret,
            })
    
    return results


def run_backtest_t2_confirm(daily_data, stock_info, industry_stocks, min_t2_open_ret: float = 0.0):
    """
    新策略：T+2日开盘确认后买入
    
    时间线：
    - T日：信号日
    - T+1日：观察日（不买入）
    - T+2日：开盘确认强势后买入
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
            t2_open = open_price[t2_idx]
            
            t2_open_ret = (t2_open - t0_close) / t0_close * 100
            
            if t2_open_ret < min_t2_open_ret:
                continue
            
            buy_price = t2_open
            
            day1_high = high[t2_idx] if t2_idx < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            highest_price = buy_price
            sell_idx = None
            
            for d in range(1, 21):
                if t2_idx + d >= len(close):
                    break
                
                current_price = close[t2_idx + d]
                current_high = high[t2_idx + d]
                
                if current_high > highest_price:
                    highest_price = current_high
                
                drawdown = (highest_price - current_price) / highest_price * 100
                if drawdown >= 5:
                    sell_idx = t2_idx + d
                    break
            
            if sell_idx is None:
                sell_idx = min(t2_idx + 20, len(close) - 1)
            
            sell_price = close[sell_idx]
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'day1_high_ret': day1_high_ret,
                't2_open_ret': t2_open_ret,
            })
    
    return results


def run_backtest_t1_open(daily_data, stock_info, industry_stocks, min_t1_open_ret: float = 0.0):
    """
    方案3：T+1日开盘买入
    
    时间线：
    - T日：信号日
    - T+1日：开盘买入（如果开盘涨幅达标）
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
            
            if t1_idx >= len(close) - 20:
                continue
            
            t0_close = close[t0_idx]
            t1_open = open_price[t1_idx]
            
            t1_open_ret = (t1_open - t0_close) / t0_close * 100
            
            if t1_open_ret < min_t1_open_ret:
                continue
            
            buy_price = t1_open
            
            day1_high = high[t1_idx] if t1_idx < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            highest_price = buy_price
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
            ret = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'return': ret,
                'day1_high_ret': day1_high_ret,
                't1_open_ret': t1_open_ret,
            })
    
    return results


def main():
    print("\n" + "="*70)
    print("不同买入时机对比测试")
    print("="*70)
    print("时间范围: 2023.5.4 - 2024.9.24 (熊市)")
    
    stock_info, daily_data, industry_stocks = load_data("2023-05-04", "2024-09-24")
    
    print("\n" + "="*70)
    print("【方案对比】")
    print("="*70)
    
    print("\n方案1: 原策略 - T+1日收盘买入")
    results1 = run_backtest_original(daily_data, stock_info, industry_stocks)
    if results1:
        returns1 = np.array([r['return'] for r in results1])
        print(f"  交易数: {len(returns1)}")
        print(f"  胜率: {np.sum(returns1 > 0) / len(returns1) * 100:.1f}%")
        print(f"  平均收益: {np.mean(returns1):+.2f}%")
    
    print("\n方案2: T+1日开盘买入（无过滤）")
    results2 = run_backtest_t1_open(daily_data, stock_info, industry_stocks, min_t1_open_ret=-10.0)
    if results2:
        returns2 = np.array([r['return'] for r in results2])
        print(f"  交易数: {len(returns2)}")
        print(f"  胜率: {np.sum(returns2 > 0) / len(returns2) * 100:.1f}%")
        print(f"  平均收益: {np.mean(returns2):+.2f}%")
    
    print("\n方案3: T+1日开盘买入（开盘涨幅>=0%）")
    results3 = run_backtest_t1_open(daily_data, stock_info, industry_stocks, min_t1_open_ret=0.0)
    if results3:
        returns3 = np.array([r['return'] for r in results3])
        print(f"  交易数: {len(returns3)}")
        print(f"  胜率: {np.sum(returns3 > 0) / len(returns3) * 100:.1f}%")
        print(f"  平均收益: {np.mean(returns3):+.2f}%")
    
    print("\n方案4: T+2日开盘买入（无过滤）")
    results4 = run_backtest_t2_confirm(daily_data, stock_info, industry_stocks, min_t2_open_ret=-10.0)
    if results4:
        returns4 = np.array([r['return'] for r in results4])
        print(f"  交易数: {len(returns4)}")
        print(f"  胜率: {np.sum(returns4 > 0) / len(returns4) * 100:.1f}%")
        print(f"  平均收益: {np.mean(returns4):+.2f}%")
    
    print("\n方案5: T+2日开盘买入（开盘涨幅>=0%）")
    results5 = run_backtest_t2_confirm(daily_data, stock_info, industry_stocks, min_t2_open_ret=0.0)
    if results5:
        returns5 = np.array([r['return'] for r in results5])
        print(f"  交易数: {len(returns5)}")
        print(f"  胜率: {np.sum(returns5 > 0) / len(returns5) * 100:.1f}%")
        print(f"  平均收益: {np.mean(returns5):+.2f}%")
    
    print("\n" + "="*70)
    print("【T+2日开盘涨幅阈值测试】")
    print("="*70)
    
    thresholds = [-2.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0]
    
    print(f"\n{'开盘阈值':>10} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*50)
    
    for min_open_ret in thresholds:
        results = run_backtest_t2_confirm(daily_data, stock_info, industry_stocks, min_open_ret)
        
        if not results:
            continue
        
        returns = np.array([r['return'] for r in results])
        n = len(returns)
        win_rate = np.sum(returns > 0) / n * 100
        avg_ret = np.mean(returns)
        
        total_profit = np.sum(returns[returns > 0])
        total_loss = np.abs(np.sum(returns[returns < 0]))
        pf = total_profit / total_loss if total_loss > 0 else float('inf')
        
        print(f"{min_open_ret:>+9.1f}% {n:>8} {win_rate:>7.1f}% {avg_ret:>+9.2f}% {pf:>8.2f}")
    
    print("\n" + "="*70)
    print("【核心问题分析】")
    print("="*70)
    print("""
问题本质：
- 信号日(T日)确认后，T+1日买入
- "强势"是T+2日的表现，买入时未知
- 无论T+1日收盘买入还是开盘买入，都无法预判T+2日的强势

可能的解决方向：
1. 接受不确定性，优化止盈止损策略
2. 分批建仓：T+1日买入部分仓位，T+2日确认强势后加仓
3. 放弃"预判强势"，改为"跟随强势"：T+2日强势确认后追入
4. 寻找其他预测因子（如分时数据、资金流向等）
""")


if __name__ == "__main__":
    main()
