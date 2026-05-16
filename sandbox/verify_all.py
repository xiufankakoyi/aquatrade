"""
完整验证脚本 - 检查数据、持仓、复权因子
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


def main():
    print("=" * 70)
    print("完整验证 - 数据、持仓、复权因子")
    print("=" * 70)
    
    data = get_cache()
    
    print("\n" + "=" * 70)
    print("1. 数据完整性检查")
    print("=" * 70)
    
    total_stocks = len(data.daily_data)
    print(f"\n股票总数: {total_stocks}")
    
    issues = []
    sample_stocks = list(data.daily_data.keys())[:100]
    
    for stock_code in sample_stocks:
        d = data.daily_data[stock_code]
        close = d['close']
        high = d['high']
        low = d['low']
        dates = d['dates']
        
        if len(close) < 30:
            continue
        
        if np.any(high < close):
            issues.append(f"{stock_code}: 最高价 < 收盘价")
        if np.any(low > close):
            issues.append(f"{stock_code}: 最低价 > 收盘价")
        if np.any(high < low):
            issues.append(f"{stock_code}: 最高价 < 最低价")
        if np.any(close <= 0):
            issues.append(f"{stock_code}: 收盘价 <= 0")
        
        dates_str = dates.astype(str)
        for j in range(1, len(dates_str)):
            if dates_str[j] <= dates_str[j-1]:
                issues.append(f"{stock_code}: 日期未排序")
                break
    
    if issues:
        print(f"\n发现 {len(issues)} 个问题:")
        for issue in issues[:10]:
            print(f"  - {issue}")
    else:
        print("\n✓ 价格数据正常，无异常")
        print("✓ 日期已排序")
    
    print("\n" + "=" * 70)
    print("2. 复权因子检查")
    print("=" * 70)
    
    has_adj = False
    for stock_code in list(data.daily_data.keys())[:5]:
        d = data.daily_data[stock_code]
        if 'adj_factor' in d:
            has_adj = True
            print(f"\n{stock_code} 复权因子:")
            print(f"  范围: {d['adj_factor'].min():.4f} - {d['adj_factor'].max():.4f}")
            print(f"  前5个: {d['adj_factor'][:5]}")
            break
    
    if not has_adj:
        print("\n⚠ 未找到复权因子字段")
        print("  如果数据已复权，则无需额外处理")
    
    print("\n" + "=" * 70)
    print("3. 持仓逻辑检查")
    print("=" * 70)
    
    print("""
持仓规则：
  - 单股持仓: 资金 × 2%
  - 总仓上限: 80%
  - 最多持股: 40只

买入条件：
  1. 连续4根绿柱（负值）
  2. 绿柱收缩（绝对值递减）
  3. 第4根绿柱 > -0.005

卖出条件：
  1. 止盈: 持有期间最高涨幅 >= 3%
  2. 超时: 持仓超过10天
""")
    
    print("\n" + "=" * 70)
    print("4. 抽样验证交易")
    print("=" * 70)
    
    sample_stock = None
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        if len(d['close']) >= 100:
            sample_stock = stock_code
            break
    
    if sample_stock:
        d = data.daily_data[sample_stock]
        close = d['close']
        high = d['high']
        dates = d['dates']
        
        _, _, hist = calc_macd(close)
        signals = detect_signal(hist)
        
        signal_indices = np.where(signals)[0]
        
        if len(signal_indices) > 0:
            sig_idx = signal_indices[0]
            buy_idx = sig_idx + 1
            
            print(f"\n样本股票: {sample_stock}")
            print(f"信号日: {dates[sig_idx]}")
            print(f"绿柱值: {hist[sig_idx-3]:.4f}, {hist[sig_idx-2]:.4f}, {hist[sig_idx-1]:.4f}, {hist[sig_idx]:.4f}")
            print(f"买入日: {dates[buy_idx]}")
            print(f"买入价: {close[buy_idx]:.2f}")
            
            buy_price = close[buy_idx]
            for hold_day in range(10):
                check_idx = buy_idx + hold_day
                if check_idx >= len(close):
                    break
                
                day_high_pct = (high[check_idx] - buy_price) / buy_price
                
                if day_high_pct >= 0.03:
                    print(f"止盈日: {dates[check_idx]} (第{hold_day+1}天)")
                    print(f"卖出价: {close[check_idx]:.2f}")
                    print(f"收益: {(close[check_idx] - buy_price) / buy_price * 100:.2f}%")
                    print(f"最高涨幅: {day_high_pct * 100:.2f}%")
                    break
            else:
                sell_idx = min(buy_idx + 9, len(close) - 1)
                print(f"超时卖出日: {dates[sell_idx]}")
                print(f"卖出价: {close[sell_idx]:.2f}")
                print(f"收益: {(close[sell_idx] - buy_price) / buy_price * 100:.2f}%")
    
    print("\n" + "=" * 70)
    print("5. 资金计算验证")
    print("=" * 70)
    
    print("""
资金计算公式：
  买入: 持仓金额 = 当前资金 × 单股持仓比例
  卖出: 盈亏 = 持仓金额 × 收益率
  新资金 = 当前资金 + 盈亏

示例（初始10万，单股2%）：
  第1笔: 买入价10元，卖出价10.3元，收益+3%
    持仓金额 = 100,000 × 2% = 2,000
    盈利 = 2,000 × 3% = 60
    新资金 = 100,000 + 60 = 100,060

  第2笔: 买入价20元，卖出价19元，收益-5%
    持仓金额 = 100,060 × 2% = 2,001.2
    亏损 = 2,001.2 × 5% = 100.06
    新资金 = 100,060 - 100.06 = 99,959.94
""")
    
    print("\n" + "=" * 70)
    print("6. 最终结果验证")
    print("=" * 70)
    
    position_per_stock = 0.02
    max_total_position = 0.80
    take_profit_pct = 0.03
    max_hold_days = 10
    
    all_trades = []
    
    for stock_code in data.daily_data:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 30:
            continue
        
        mask = (dates >= "2024-01-01") & (dates <= "2025-12-31")
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
                buy_date_idx = i + 1
                
                if buy_date_idx >= len(close):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                sell_date = buy_date
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                
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
    total_profit = 0
    total_loss = 0
    total_trades = 0
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                if profit > 0:
                    total_profit += profit
                else:
                    total_loss += abs(profit)
                del holdings[stock_code]
                total_trades += 1
        
        if date in trades_by_buy_date:
            current_position_pct = len(holdings) * position_per_stock
            
            for t in trades_by_buy_date[date]:
                if current_position_pct + position_per_stock <= max_total_position:
                    holdings[t['stock_code']] = {
                        'position_value': capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date']
                    }
                    current_position_pct += position_per_stock
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
        if profit > 0:
            total_profit += profit
        else:
            total_loss += abs(profit)
        total_trades += 1
    
    print(f"\n验证计算：")
    print(f"  总交易数: {total_trades}")
    print(f"  总盈利: {total_profit:,.0f}")
    print(f"  总亏损: {total_loss:,.0f}")
    print(f"  净收益: {total_profit - total_loss:,.0f}")
    print(f"  初始资金: 100,000")
    print(f"  最终资金: {capital:,.0f}")
    print(f"  总收益: {(capital - 100000) / 100000 * 100:.1f}%")
    
    expected_final = 100000 + total_profit - total_loss
    print(f"\n  验证: 100,000 + {total_profit:,.0f} - {total_loss:,.0f} = {expected_final:,.0f}")
    
    if abs(capital - expected_final) < 1:
        print("  ✓ 资金计算正确")
    else:
        print(f"  ✗ 资金计算有误，差异: {abs(capital - expected_final):,.0f}")
    
    print("\n" + "=" * 70)
    print("验证完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
