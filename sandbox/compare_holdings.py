"""
对比不同持仓配置的回测表现
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from collections import defaultdict
from numba import njit

from data_cache import get_cache, PreloadedData


@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    multiplier = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema


@njit
def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return dif, dea, histogram


@njit
def detect_signal(bars: np.ndarray) -> np.ndarray:
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3):
                if b3 > -0.005:
                    signals[i] = True
    
    return signals


def run_backtest(data: PreloadedData, start_date: str, end_date: str,
                 position_per_stock: float, max_total_position: float,
                 max_hold_days: int = 10, take_profit_pct: float = 0.03,
                 trailing_pct: float = 0.02):
    
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sell_date = buy_date
                peak_price = buy_price
                triggered_trailing = False
                sold = False
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        triggered_trailing = True
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= trailing_pct:
                            sell_price = close[check_idx]
                            sell_date = str(dates[check_idx])
                            sold = True
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sold = True
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret
                })
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    capital = 100000.0
    holdings = {}
    equity_curve = []
    executed_trades = []
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                executed_trades.append({
                    'stock_code': stock_code,
                    'return': h['return']
                })
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    continue
                
                if current_position_pct + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position_pct += position_per_stock
        
        equity_curve.append({'date': date, 'equity': capital})
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
        executed_trades.append({
            'stock_code': stock_code,
            'return': h['return']
        })
    
    return equity_curve, executed_trades


def calculate_metrics(equity_curve: list, trades: list):
    if len(equity_curve) < 2:
        return {}
    
    df = pd.DataFrame(equity_curve)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    df['return'] = df['equity'].pct_change()
    df = df.dropna()
    
    returns = df['return'].values
    
    total_return = (equity_curve[-1]['equity'] - 100000) / 100000 * 100
    
    days = len(equity_curve)
    annualized_return = ((equity_curve[-1]['equity'] / 100000) ** (252 / days) - 1) * 100
    
    equity_values = [e['equity'] for e in equity_curve]
    peak = equity_values[0]
    max_dd = 0
    for eq in equity_values:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    max_drawdown = max_dd * 100
    
    if len(returns) > 1 and np.std(returns) > 0:
        rf = 0.02 / 252
        excess_returns = returns - rf
        sharpe = np.mean(excess_returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe = 0
    
    volatility = np.std(returns) * np.sqrt(252) * 100
    
    if trades:
        trade_returns = [t['return'] for t in trades]
        wins = [r for r in trade_returns if r > 0]
        losses = [r for r in trade_returns if r < 0]
        win_rate = len(wins) / len(trades) * 100
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0
        avg_return = np.mean(trade_returns) * 100
    else:
        win_rate = 0
        profit_factor = 0
        avg_return = 0
    
    return {
        'totalReturn': total_return,
        'annualizedReturn': annualized_return,
        'maxDrawdown': max_drawdown,
        'sharpeRatio': sharpe,
        'volatility': volatility,
        'totalTrades': len(trades),
        'winRate': win_rate,
        'profitFactor': profit_factor,
        'avgReturn': avg_return,
        'finalEquity': equity_curve[-1]['equity']
    }


def main():
    data = get_cache()
    
    start_date = "2022-01-07"
    end_date = "2024-09-22"
    
    configs = [
        {'name': '5只(90%仓位)', 'max_holdings': 5, 'total_position': 0.90, 
         'position_per_stock': 0.90 / 5},
        {'name': '10只(满仓)', 'max_holdings': 10, 'total_position': 1.00,
         'position_per_stock': 1.00 / 10},
        {'name': '15只(26%仓位)', 'max_holdings': 15, 'total_position': 0.26,
         'position_per_stock': 0.26 / 15},
        {'name': '22只(满仓)', 'max_holdings': 22, 'total_position': 1.00,
         'position_per_stock': 1.00 / 22},
    ]
    
    print("=" * 90)
    print("不同持仓配置对比")
    print("=" * 90)
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    results = []
    
    for config in configs:
        print(f"\n测试配置: {config['name']}...")
        
        equity_curve, trades = run_backtest(
            data, start_date, end_date,
            position_per_stock=config['position_per_stock'],
            max_total_position=config['total_position']
        )
        
        metrics = calculate_metrics(equity_curve, trades)
        metrics['name'] = config['name']
        metrics['max_holdings'] = config['max_holdings']
        metrics['position_per_stock'] = config['position_per_stock'] * 100
        metrics['total_position'] = config['total_position'] * 100
        results.append(metrics)
    
    print("\n" + "=" * 90)
    print("回测结果对比")
    print("=" * 90)
    
    print(f"\n{'配置':<18} {'总收益':>10} {'年化':>10} {'最大回撤':>10} {'夏普':>8} {'波动率':>10} {'交易数':>8} {'胜率':>8} {'盈亏比':>8}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['name']:<18} {r['totalReturn']:>9.2f}% {r['annualizedReturn']:>9.2f}% "
              f"{r['maxDrawdown']:>9.2f}% {r['sharpeRatio']:>8.2f} {r['volatility']:>9.2f}% "
              f"{r['totalTrades']:>8} {r['winRate']:>7.2f}% {r['profitFactor']:>8.2f}")
    
    print("\n" + "=" * 90)
    print("详细配置")
    print("=" * 90)
    
    print(f"\n{'配置':<18} {'最大持仓':>10} {'单股仓位':>10} {'总仓位上限':>12} {'最终资金':>12}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['name']:<18} {r['max_holdings']:>10}只 {r['position_per_stock']:>9.2f}% "
              f"{r['total_position']:>11.0f}% {r['finalEquity']:>12,.0f}")
    
    print("\n" + "=" * 90)
    print("风险调整后收益对比")
    print("=" * 90)
    
    print(f"\n{'配置':<18} {'收益/回撤':>12} {'夏普比率':>12} {'卡玛比率':>12}")
    print("-" * 60)
    
    for r in results:
        return_drawdown = r['totalReturn'] / r['maxDrawdown'] if r['maxDrawdown'] > 0 else 0
        calmar = r['annualizedReturn'] / r['maxDrawdown'] if r['maxDrawdown'] > 0 else 0
        print(f"{r['name']:<18} {return_drawdown:>12.2f} {r['sharpeRatio']:>12.2f} {calmar:>12.2f}")


if __name__ == "__main__":
    main()
