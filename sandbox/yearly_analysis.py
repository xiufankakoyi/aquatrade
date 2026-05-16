"""
分年度策略表现分析
"""

import numpy as np
from numba import njit
from data_cache import get_cache, PreloadedData
from collections import defaultdict


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


def collect_all_trades(data: PreloadedData, start_date: str, end_date: str,
                       take_profit_pct: float, max_hold_days: int):
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        
        if len(close) < 30:
            continue
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if signals[i]:
                signal_date = str(dates[i])
                buy_date_idx = i + 1
                
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sell_date = buy_date
                actual_hold_days = 0
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        actual_hold_days = check_idx - buy_date_idx + 1
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        actual_hold_days = hold_day + 1
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        actual_hold_days = max_hold_days
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret,
                    'hold_days': actual_hold_days
                })
    
    return all_trades


def simulate_portfolio(trades: list, position_per_stock: float, max_total_position: float,
                       initial_capital: float = 100000):
    all_dates = set()
    for t in trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    capital = initial_capital
    capital_history = {'date': [], 'capital': []}
    holdings = {}
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                capital += h['position_value'] * h['return']
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if current_position + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position += position_per_stock
        
        capital_history['date'].append(date)
        capital_history['capital'].append(capital)
    
    for stock_code in holdings:
        capital += holdings[stock_code]['position_value'] * holdings[stock_code]['return']
    
    return capital, capital_history


def analyze_period(trades: list, period_name: str):
    """分析某个时期的交易"""
    if not trades:
        print(f"\n{period_name}: 无交易")
        return None
    
    returns = np.array([t['return'] for t in trades])
    wins = returns > 0
    losses = returns < 0
    
    win_rate = np.mean(wins)
    avg_win = np.mean(returns[wins]) if np.any(wins) else 0
    avg_loss = np.mean(returns[losses]) if np.any(losses) else 0
    avg_ret = np.mean(returns)
    
    total_profit = np.sum(returns[wins])
    total_loss = abs(np.sum(returns[losses]))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    print(f"\n{period_name}:")
    print(f"  交易数: {len(trades)}")
    print(f"  胜率: {win_rate*100:.1f}%")
    print(f"  平均收益: {avg_ret*100:.2f}%")
    print(f"  盈利因子: {profit_factor:.2f}")
    print(f"  盈亏比: {avg_win/abs(avg_loss):.2f}" if avg_loss != 0 else "  盈亏比: N/A")
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'avg_return': avg_ret,
        'profit_factor': profit_factor,
        'win_loss_ratio': avg_win/abs(avg_loss) if avg_loss != 0 else 0
    }


def main():
    print("=" * 70)
    print("分年度策略表现分析")
    print("=" * 70)
    
    print("\n策略：止盈3%，最大持仓10天，单股10%，总仓80%")
    
    data = get_cache()
    
    periods = [
        ("2024全年", "2024-01-01", "2024-12-31"),
        ("2025全年", "2025-01-01", "2025-12-31"),
        ("2024上半年", "2024-01-01", "2024-06-30"),
        ("2024下半年", "2024-07-01", "2024-12-31"),
        ("2025上半年", "2025-01-01", "2025-06-30"),
        ("2025下半年", "2025-07-01", "2025-12-31"),
    ]
    
    print("\n" + "=" * 70)
    print("各时期交易统计")
    print("=" * 70)
    
    for name, start, end in periods:
        trades = collect_all_trades(data, start, end, 0.03, 10)
        analyze_period(trades, name)
    
    print("\n" + "=" * 70)
    print("模拟收益（初始10万，单股10%，总仓80%）")
    print("=" * 70)
    
    print(f"\n{'时期':^15} {'最终资金':^12} {'总收益%':^10} {'最大回撤%':^10}")
    print("-" * 50)
    
    for name, start, end in periods:
        trades = collect_all_trades(data, start, end, 0.03, 10)
        if not trades:
            continue
        
        final_cap, cap_history = simulate_portfolio(trades, 0.10, 0.80)
        total_return = (final_cap - 100000) / 100000
        
        caps = cap_history['capital']
        peak = 100000
        max_dd = 0
        for cap in caps:
            if cap > peak:
                peak = cap
            dd = (peak - cap) / peak
            if dd > max_dd:
                max_dd = dd
        
        print(f"{name:^15} {final_cap:^12,.0f} {total_return*100:^10.1f} {max_dd*100:^10.1f}")
    
    print("\n" + "=" * 70)
    print("连续模拟（从2024到2025）")
    print("=" * 70)
    
    trades_2024 = collect_all_trades(data, "2024-01-01", "2024-12-31", 0.03, 10)
    trades_2025 = collect_all_trades(data, "2025-01-01", "2025-12-31", 0.03, 10)
    
    all_trades = trades_2024 + trades_2025
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    capital = 100000
    holdings = {}
    capital_by_month = []
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                capital += h['position_value'] * h['return']
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            current_position = len(holdings) * 0.10
            
            for t in trades_by_buy_date[date]:
                if current_position + 0.10 <= 0.80:
                    holdings[t['stock_code']] = {
                        'position_value': capital * 0.10,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position += 0.10
        
        if date.endswith('-01'):
            capital_by_month.append((date[:7], capital))
    
    for stock_code in holdings:
        capital += holdings[stock_code]['position_value'] * holdings[stock_code]['return']
    
    print(f"\n初始资金: 100,000")
    print(f"最终资金: {capital:,.0f}")
    print(f"总收益: {(capital-100000)/100000*100:.1f}%")
    
    print("\n月度资金变化：")
    for month, cap in capital_by_month[-12:]:
        print(f"  {month}: {cap:,.0f}")
    
    print("\n" + "=" * 70)
    print("不同止盈比例对比（2024-2025完整）")
    print("=" * 70)
    
    print(f"\n{'止盈%':^8} {'胜率%':^8} {'盈利因子':^10} {'最终资金':^12} {'总收益%':^10}")
    print("-" * 50)
    
    for tp in [0.02, 0.03, 0.04, 0.05]:
        t = collect_all_trades(data, "2024-01-01", "2025-12-31", tp, 10)
        if not t:
            continue
        
        r = np.array([x['return'] for x in t])
        w = r > 0
        wr = np.mean(w)
        
        tp_profit = np.sum(r[w])
        tp_loss = abs(np.sum(r[~w]))
        pf = tp_profit / tp_loss if tp_loss > 0 else float('inf')
        
        final, _ = simulate_portfolio(t, 0.10, 0.80)
        ret = (final - 100000) / 100000
        
        print(f"{tp*100:^8.0f} {wr*100:^8.1f} {pf:^10.2f} {final:^12,.0f} {ret*100:^10.1f}")


if __name__ == "__main__":
    main()
