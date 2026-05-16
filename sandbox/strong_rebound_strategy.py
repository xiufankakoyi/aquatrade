"""
强势反弹策略

买点条件：
1. 主板股票（60，00开头）
2. MACD绿柱凹函数收缩（4根绿柱递增，且收缩加速）
3. MACD绿柱值 > -0.005（接近0）
4. 成交量比 >= 1.5
5. 板块内涨幅排名前20%

强势过滤：
- 买入后第1天最高涨幅 >= 3%

卖点：
- 从最高点回撤 X% 卖出（可调参数）
- 最长持有 Y 天（可调参数）
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict, List, Tuple
from dataclasses import dataclass

from config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyParams:
    """策略参数"""
    min_histogram_value: float = -0.005
    min_vol_ratio: float = 1.5
    min_rank_percentile: float = 80.0
    min_day1_high_ret: float = 3.0
    trailing_pct: float = 5.0
    max_hold_days: int = 20


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int
    win_rate: float
    avg_return: float
    median_return: float
    profit_factor: float
    avg_hold_days: float
    max_return: float
    min_return: float


def calculate_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """计算MACD"""
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
    """计算成交量均线"""
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
    """计算板块内个股排名"""
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
    """加载数据"""
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


def run_backtest(
    daily_data: dict,
    stock_info: dict,
    industry_stocks: dict,
    params: StrategyParams,
) -> Tuple[BacktestResult, List[dict]]:
    """
    运行回测
    
    Returns:
        BacktestResult: 回测统计结果
        List[dict]: 详细交易记录
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
        
        for i in range(4, len(histogram) - params.max_hold_days - 5):
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
            
            if bars[3] > params.min_histogram_value:
                continue
            
            vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
            if vol_ratio < params.min_vol_ratio:
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
            
            if stock_rank < params.min_rank_percentile:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close) - params.max_hold_days:
                continue
            
            buy_price = close[buy_idx]
            
            day1_high = high[buy_idx + 1] if buy_idx + 1 < len(high) else buy_price
            day1_high_ret = (day1_high - buy_price) / buy_price * 100
            
            if day1_high_ret < params.min_day1_high_ret:
                continue
            
            highest_price = buy_price
            sell_idx = None
            hold_days = 0
            
            for d in range(1, params.max_hold_days + 1):
                if buy_idx + d >= len(close):
                    break
                
                current_price = close[buy_idx + d]
                current_high = high[buy_idx + d]
                
                if current_high > highest_price:
                    highest_price = current_high
                
                drawdown = (highest_price - current_price) / highest_price * 100
                if drawdown >= params.trailing_pct:
                    sell_idx = buy_idx + d
                    hold_days = d
                    break
            
            if sell_idx is None:
                sell_idx = min(buy_idx + params.max_hold_days, len(close) - 1)
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
                'day1_high_ret': day1_high_ret,
            })
    
    if not results:
        return None, []
    
    returns = np.array([r['return'] for r in results])
    n = len(returns)
    win_count = np.sum(returns > 0)
    
    total_profit = np.sum(returns[returns > 0])
    total_loss = np.abs(np.sum(returns[returns < 0]))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    result = BacktestResult(
        total_trades=n,
        win_rate=win_count / n * 100,
        avg_return=np.mean(returns),
        median_return=np.median(returns),
        profit_factor=profit_factor,
        avg_hold_days=np.mean([r['hold_days'] for r in results]),
        max_return=np.max(returns),
        min_return=np.min(returns),
    )
    
    return result, results


def grid_search(
    daily_data: dict,
    stock_info: dict,
    industry_stocks: dict,
    trailing_range: List[float] = None,
    hold_days_range: List[int] = None,
    day1_threshold_range: List[float] = None,
):
    """网格搜索最优参数"""
    
    if trailing_range is None:
        trailing_range = [3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    if hold_days_range is None:
        hold_days_range = [10, 15, 20, 25, 30]
    if day1_threshold_range is None:
        day1_threshold_range = [2.0, 2.5, 3.0, 3.5, 4.0]
    
    print("\n" + "="*70)
    print("网格搜索最优参数")
    print("="*70)
    
    print(f"\n{'回撤%':>8} {'持仓天数':>8} {'第1天阈值':>10} {'交易数':>8} {'胜率':>8} {'平均收益':>10} {'盈利因子':>8}")
    print("-"*70)
    
    best_result = None
    best_params = None
    all_results = []
    
    for trailing_pct in trailing_range:
        for max_hold_days in hold_days_range:
            for min_day1_ret in day1_threshold_range:
                params = StrategyParams(
                    trailing_pct=trailing_pct,
                    max_hold_days=max_hold_days,
                    min_day1_high_ret=min_day1_ret,
                )
                
                result, _ = run_backtest(daily_data, stock_info, industry_stocks, params)
                
                if result:
                    all_results.append({
                        'trailing_pct': trailing_pct,
                        'max_hold_days': max_hold_days,
                        'min_day1_ret': min_day1_ret,
                        'result': result,
                    })
                    
                    print(f"{trailing_pct:>7.1f}% {max_hold_days:>8} {min_day1_ret:>9.1f}% "
                          f"{result.total_trades:>8} {result.win_rate:>7.1f}% "
                          f"{result.avg_return:>+9.2f}% {result.profit_factor:>8.2f}")
                    
                    if best_result is None or result.avg_return > best_result.avg_return:
                        best_result = result
                        best_params = params
    
    print("\n" + "="*70)
    print("最优参数")
    print("="*70)
    
    if best_params:
        print(f"\n  回撤止盈: {best_params.trailing_pct}%")
        print(f"  最大持仓: {best_params.max_hold_days} 天")
        print(f"  第1天阈值: {best_params.min_day1_high_ret}%")
        print(f"\n  交易数: {best_result.total_trades}")
        print(f"  胜率: {best_result.win_rate:.1f}%")
        print(f"  平均收益: {best_result.avg_return:+.2f}%")
        print(f"  盈利因子: {best_result.profit_factor:.2f}")
    
    return best_params, best_result, all_results


def main():
    print("\n" + "="*70)
    print("强势反弹策略 - 测试集 2025.1 - 2025.10")
    print("="*70)
    
    stock_info, daily_data, industry_stocks = load_data("2025-01-01", "2025-10-31")
    
    print("\n" + "="*70)
    print("默认参数回测")
    print("="*70)
    
    params = StrategyParams()
    result, trades = run_backtest(daily_data, stock_info, industry_stocks, params)
    
    if result:
        print(f"\n  交易数: {result.total_trades}")
        print(f"  胜率: {result.win_rate:.1f}%")
        print(f"  平均收益: {result.avg_return:+.2f}%")
        print(f"  中位收益: {result.median_return:+.2f}%")
        print(f"  盈利因子: {result.profit_factor:.2f}")
        print(f"  平均持仓: {result.avg_hold_days:.1f} 天")
    
    grid_search(daily_data, stock_info, industry_stocks)


if __name__ == "__main__":
    main()
