"""
凯利公式持仓策略测试 - 正确的并发持仓模拟
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
    """
    收集所有交易，记录买入日期和卖出日期
    """
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
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
                    'signal_date': signal_date,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'return': ret,
                    'hold_days': actual_hold_days
                })
    
    return all_trades


def simulate_portfolio(trades: list, position_per_stock: float, max_total_position: float,
                       initial_capital: float = 100000):
    """
    模拟组合 - 按日期顺序处理买入和卖出
    """
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


def main():
    print("=" * 70)
    print("凯利公式持仓策略测试")
    print("=" * 70)
    
    print("\n凯利公式: f* = (bp - q) / b")
    print("  b = 盈亏比, p = 胜率, q = 1-p")
    
    data = get_cache()
    
    print("\n" + "=" * 70)
    print("基础策略：止盈3%，最大持仓10天")
    print("=" * 70)
    
    trades = collect_all_trades(data, "2024-01-01", "2025-12-31", 0.03, 10)
    
    print(f"\n总交易数: {len(trades)}")
    
    returns = np.array([t['return'] for t in trades])
    wins = returns > 0
    losses = returns < 0
    
    win_rate = np.mean(wins)
    avg_win = np.mean(returns[wins]) if np.any(wins) else 0
    avg_loss = np.mean(returns[losses]) if np.any(losses) else 0
    
    print(f"胜率: {win_rate*100:.1f}%")
    print(f"平均盈利: {avg_win*100:.2f}%")
    print(f"平均亏损: {avg_loss*100:.2f}%")
    
    b = avg_win / abs(avg_loss)
    print(f"盈亏比: {b:.2f}")
    
    p = win_rate
    q = 1 - p
    kelly = max(0, (b * p - q) / b)
    
    print(f"\n凯利比例: {kelly*100:.1f}%")
    print(f"半凯利比例: {kelly*50:.1f}%")
    
    print("\n" + "=" * 70)
    print("并发持仓分析")
    print("=" * 70)
    
    trades_by_buy = defaultdict(list)
    for t in trades:
        trades_by_buy[t['buy_date']].append(t)
    
    signals_per_day = [len(trades_by_buy[d]) for d in trades_by_buy]
    print(f"\n每日买入信号数：")
    print(f"  平均: {np.mean(signals_per_day):.1f}")
    print(f"  中位数: {np.median(signals_per_day):.0f}")
    print(f"  最大: {np.max(signals_per_day)}")
    
    print("\n" + "=" * 70)
    print("不同持仓策略模拟（初始资金10万）")
    print("=" * 70)
    
    print(f"\n{'单股持仓%':^10} {'总仓上限%':^10} {'最终资金':^12} {'总收益%':^10} {'最大回撤%':^10}")
    print("-" * 55)
    
    test_cases = [
        (0.05, 0.30),
        (0.05, 0.50),
        (0.10, 0.30),
        (0.10, 0.50),
        (0.10, 0.80),
        (0.15, 0.50),
        (0.15, 0.80),
        (0.20, 0.80),
    ]
    
    for pos_per_stock, max_total in test_cases:
        final_cap, cap_history = simulate_portfolio(trades, pos_per_stock, max_total)
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
        
        print(f"{pos_per_stock*100:^10.0f} {max_total*100:^10.0f} {final_cap:^12,.0f} {total_return*100:^10.1f} {max_dd*100:^10.1f}")
    
    print("\n" + "=" * 70)
    print("凯利策略（有上限）")
    print("=" * 70)
    
    print(f"\n{'策略':^12} {'单股持仓%':^10} {'总仓上限%':^10} {'最终资金':^12} {'总收益%':^10}")
    print("-" * 60)
    
    kelly_strategies = [
        ("凯利(上限80%)", kelly, 0.80),
        ("凯利(上限100%)", kelly, 1.00),
        ("半凯利(上限50%)", kelly/2, 0.50),
        ("半凯利(上限80%)", kelly/2, 0.80),
        ("1/4凯利(上限50%)", kelly/4, 0.50),
    ]
    
    for name, pos, max_total in kelly_strategies:
        final_cap, _ = simulate_portfolio(trades, pos, max_total)
        total_return = (final_cap - 100000) / 100000
        print(f"{name:^12} {pos*100:^10.1f} {max_total*100:^10.0f} {final_cap:^12,.0f} {total_return*100:^10.1f}")
    
    print("\n" + "=" * 70)
    print("不同止盈比例的凯利分析")
    print("=" * 70)
    
    print(f"\n{'止盈%':^8} {'胜率%':^8} {'盈亏比':^8} {'凯利%':^8} {'半凯利%':^10}")
    print("-" * 45)
    
    for tp in [0.02, 0.03, 0.04, 0.05]:
        t = collect_all_trades(data, "2024-01-01", "2025-12-31", tp, 10)
        if not t:
            continue
        r = np.array([x['return'] for x in t])
        w = r > 0
        l = r < 0
        wr = np.mean(w)
        aw = np.mean(r[w]) if np.any(w) else 0
        al = np.mean(r[l]) if np.any(l) else 0
        ratio = aw / abs(al) if al != 0 else 0
        k = max(0, (ratio * wr - (1-wr)) / ratio) if ratio > 0 else 0
        print(f"{tp*100:^8.0f} {wr*100:^8.1f} {ratio:^8.2f} {k*100:^8.1f} {k*50:^10.1f}")


if __name__ == "__main__":
    main()
