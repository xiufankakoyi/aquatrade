"""
导入指数数据并生成回测曲线图 - 优化版（移动止盈+背离卖点）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from numba import njit
from collections import defaultdict

from data_cache import get_cache, PreloadedData

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


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
def calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    rsi = np.zeros(n)
    gains = np.zeros(n)
    losses = np.zeros(n)
    
    for i in range(1, n):
        change = close[i] - close[i-1]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = -change
    
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    for i in range(period, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    rsi[:period] = 50
    return rsi


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


@njit
def find_local_peaks(arr: np.ndarray, window: int = 5) -> np.ndarray:
    n = len(arr)
    peaks = np.zeros(n, dtype=np.bool_)
    
    for i in range(window, n - window):
        is_peak = True
        for j in range(-window, window + 1):
            if j != 0 and arr[i] <= arr[i + j]:
                is_peak = False
                break
        peaks[i] = is_peak
    
    return peaks


def run_backtest(data: PreloadedData, start_date: str, end_date: str,
                 position_per_stock: float = 0.18, max_holdings: int = 5,
                 take_profit_pct: float = 0.03, max_hold_days: int = 10,
                 trailing_pct: float = 0.02):
    """
    运行回测 - 移动止盈+背离卖点策略
    
    仓位管理：最多持有5只股票，每只18%仓位，总仓位90%
    
    卖点逻辑：
    1. 移动止盈：浮盈达到3%后启动，回撤2%止盈
    2. 背离信号：触发移动止盈后，若出现MACD/RSI顶背离则提前卖出
    
    选股逻辑：
    - 按股票代码字典序排序，确保结果可复现
    - 每天优先买入排序靠前的股票
    """
    
    all_trades = []
    
    sorted_stock_codes = sorted(data.daily_data.keys())
    
    for stock_code in sorted_stock_codes:
        d = data.daily_data[stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        rsi = calc_rsi(close, period=14)
        peaks = find_local_peaks(close, window=5)
        signals = detect_signal(hist)
        
        mask = (dates >= start_date) & (dates <= end_date)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        dates = dates[mask]
        hist = hist[mask]
        rsi = rsi[mask]
        peaks = peaks[mask]
        signals = signals[mask]
        
        if len(close) < 50:
            continue
        
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
                sell_reason = "timeout"
                hold_days = 0
                
                for hold_day in range(max_hold_days):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sell_reason = "timeout"
                        hold_days = hold_day
                        sold = True
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= take_profit_pct:
                        triggered_trailing = True
                    
                    divergence_sell = False
                    if peaks[check_idx]:
                        prev_peak_idx = -1
                        for j in range(check_idx - 1, max(0, check_idx - 30), -1):
                            if peaks[j]:
                                prev_peak_idx = j
                                break
                        
                        if prev_peak_idx > 0 and close[check_idx] > close[prev_peak_idx]:
                            if hist[check_idx] < hist[prev_peak_idx]:
                                divergence_sell = True
                            if rsi[check_idx] < rsi[prev_peak_idx] and rsi[check_idx] > 75:
                                divergence_sell = True
                    
                    if divergence_sell and triggered_trailing:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sell_reason = "divergence"
                        hold_days = hold_day + 1
                        sold = True
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= trailing_pct:
                            sell_price = close[check_idx]
                            sell_date = str(dates[check_idx])
                            sell_reason = "trailing_stop"
                            hold_days = hold_day + 1
                            sold = True
                            break
                    
                    if hold_day == max_hold_days - 1:
                        sell_price = close[check_idx]
                        sell_date = str(dates[check_idx])
                        sell_reason = "timeout"
                        hold_days = max_hold_days
                        sold = True
                
                if sell_date == buy_date:
                    continue
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'return': ret,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'hold_days': hold_days,
                    'sell_reason': sell_reason,
                    'max_profit': (peak_price - buy_price) / buy_price,
                })
    
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    for date in trades_by_buy_date:
        trades_by_buy_date[date].sort(key=lambda x: x['stock_code'])
    
    initial_capital = 100000.0
    capital = initial_capital
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
                    'buy_date': h['buy_date'],
                    'sell_date': date,
                    'return': h['return'],
                    'buy_price': h['buy_price'],
                    'sell_price': h['sell_price'],
                    'hold_days': h['hold_days'],
                    'sell_reason': h['sell_reason'],
                    'max_profit': h['max_profit'],
                    'position_value': h['position_value'],
                    'profit': profit,
                })
                del holdings[stock_code]
        
        if date in trades_by_buy_date:
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    continue
                
                if len(holdings) < max_holdings:
                    holdings[t['stock_code']] = {
                        'position_value': initial_capital * position_per_stock,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                        'buy_date': t['buy_date'],
                        'buy_price': t['buy_price'],
                        'sell_price': t['sell_price'],
                        'hold_days': t['hold_days'],
                        'sell_reason': t['sell_reason'],
                        'max_profit': t['max_profit'],
                    }
        
        equity_curve.append({'date': date, 'equity': capital})
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
        executed_trades.append({
            'stock_code': stock_code,
            'buy_date': h['buy_date'],
            'sell_date': h['sell_date'],
            'return': h['return'],
            'buy_price': h['buy_price'],
            'sell_price': h['sell_price'],
            'hold_days': h['hold_days'],
            'sell_reason': h['sell_reason'],
            'max_profit': h['max_profit'],
            'position_value': h['position_value'],
            'profit': profit,
        })
    
    return equity_curve, executed_trades


def load_benchmark_from_arcticdb(start_date: str, end_date: str, initial_capital: float = 100000, symbol: str = '000001.SH'):
    """从ArcticDB加载指数基准数据
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        symbol: 指数代码，默认上证指数，可选 '000852.SH'(中证1000), '000300.SH'(沪深300)等
    """
    try:
        from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
        
        arctic = get_arctic_instance_for_library('market_data')
        
        if 'market_data' not in arctic.list_libraries():
            print("market_data库不存在")
            return None
        
        lib = arctic['market_data']
        
        if symbol not in lib.list_symbols():
            print(f"{symbol}数据不存在")
            return None
        
        item = lib.read(symbol, date_range=(pd.Timestamp(start_date), pd.Timestamp(end_date)))
        df = item.data
        
        if df.empty:
            print("数据为空")
            return None
        
        df = df.sort_index()
        
        benchmark_curve = []
        first_close = df['close'].iloc[0]
        
        for idx, row in df.iterrows():
            date = idx.strftime('%Y-%m-%d')
            close = row['close']
            equity = initial_capital * (close / first_close)
            benchmark_curve.append({'date': date, 'equity': equity})
        
        return benchmark_curve
        
    except Exception as e:
        print(f"从ArcticDB加载基准数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_metrics(equity_curve: list):
    """计算策略指标"""
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
    
    return {
        'totalReturn': total_return,
        'annualizedReturn': annualized_return,
        'maxDrawdown': max_drawdown,
        'sharpeRatio': sharpe,
        'volatility': volatility
    }


def calculate_trade_metrics(trades: list):
    """计算交易统计"""
    if not trades:
        return {'winRate': 0, 'profitFactor': 0, 'avgReturn': 0, 'totalTrades': 0}
    
    returns = [t['return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    win_rate = len(wins) / len(returns) * 100
    total_profit = sum(wins)
    total_loss = abs(sum(losses))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    avg_return = np.mean(returns) * 100
    
    return {
        'winRate': win_rate,
        'profitFactor': profit_factor,
        'avgReturn': avg_return,
        'totalTrades': len(trades)
    }


def export_trade_records(trades: list, output_path: str):
    """导出交易记录到CSV文件"""
    if not trades:
        print("无交易记录可导出")
        return
    
    df = pd.DataFrame(trades)
    
    df = df[['stock_code', 'buy_date', 'buy_price', 'sell_date', 'sell_price', 
             'hold_days', 'sell_reason', 'return', 'max_profit', 'position_value', 'profit']]
    
    df.columns = ['股票代码', '买入日期', '买入价格', '卖出日期', '卖出价格',
                  '持仓天数', '卖出原因', '收益率', '最大浮盈', '持仓金额', '盈亏金额']
    
    df['收益率'] = df['收益率'] * 100
    df['最大浮盈'] = df['最大浮盈'] * 100
    
    df['收益率'] = df['收益率'].round(2)
    df['最大浮盈'] = df['最大浮盈'].round(2)
    df['买入价格'] = df['买入价格'].round(2)
    df['卖出价格'] = df['卖出价格'].round(2)
    df['持仓金额'] = df['持仓金额'].round(2)
    df['盈亏金额'] = df['盈亏金额'].round(2)
    
    df = df.sort_values('买入日期')
    
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n交易记录已导出: {output_path}")
    print(f"  总交易数: {len(df)}")
    print(f"  盈利交易: {len(df[df['收益率'] > 0])}")
    print(f"  亏损交易: {len(df[df['收益率'] < 0])}")


def print_trade_summary(trades: list):
    """打印交易统计摘要"""
    if not trades:
        return
    
    sell_reasons = defaultdict(list)
    for t in trades:
        sell_reasons[t['sell_reason']].append(t['return'])
    
    print("\n" + "=" * 70)
    print("卖出原因统计")
    print("=" * 70)
    
    print(f"\n{'卖出原因':^15} {'交易数':^8} {'占比%':^8} {'胜率%':^8} {'平均收益%':^10}")
    print("-" * 55)
    
    for reason, returns in sorted(sell_reasons.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(returns)
        pct = count / len(trades) * 100
        wins = [r for r in returns if r > 0]
        win_rate = len(wins) / count * 100 if count > 0 else 0
        avg_ret = np.mean(returns) * 100
        
        reason_cn = {
            'trailing_stop': '移动止盈',
            'divergence': '背离信号',
            'timeout': '超时卖出'
        }.get(reason, reason)
        
        print(f"{reason_cn:^15} {count:^8} {pct:^8.1f} {win_rate:^8.1f} {avg_ret:^10.2f}")


def plot_backtest_curve(equity_curve: list, benchmark_curve: list, output_path: str):
    """绘制回测曲线图 - 日期对齐"""
    
    strategy_df = pd.DataFrame(equity_curve)
    strategy_df['date'] = pd.to_datetime(strategy_df['date'])
    strategy_df = strategy_df.sort_values('date')
    
    benchmark_df = None
    if benchmark_curve:
        benchmark_df = pd.DataFrame(benchmark_curve)
        benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
        benchmark_df = benchmark_df.sort_values('date')
    
    if benchmark_df is not None:
        start_date = max(strategy_df['date'].min(), benchmark_df['date'].min())
        end_date = min(strategy_df['date'].max(), benchmark_df['date'].max())
        
        strategy_df = strategy_df[(strategy_df['date'] >= start_date) & (strategy_df['date'] <= end_date)].copy()
        benchmark_df = benchmark_df[(benchmark_df['date'] >= start_date) & (benchmark_df['date'] <= end_date)].copy()
    
    strategy_df['nav'] = strategy_df['equity'] / strategy_df['equity'].iloc[0]
    
    if benchmark_df is not None and len(benchmark_df) > 0:
        benchmark_df['nav'] = benchmark_df['equity'] / benchmark_df['equity'].iloc[0]
    
    print(f"\n日期对齐后:")
    print(f"  策略日期范围: {strategy_df['date'].min().date()} 到 {strategy_df['date'].max().date()}")
    print(f"  策略数据点: {len(strategy_df)}")
    if benchmark_df is not None:
        print(f"  基准日期范围: {benchmark_df['date'].min().date()} 到 {benchmark_df['date'].max().date()}")
        print(f"  基准数据点: {len(benchmark_df)}")
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1, 1]})
    
    ax1 = axes[0]
    ax1.plot(strategy_df['date'], strategy_df['nav'], label='MACD绿柱收缩策略(优化版)', color='#2E86AB', linewidth=1.5)
    
    if benchmark_df is not None and len(benchmark_df) > 0:
        ax1.plot(benchmark_df['date'], benchmark_df['nav'], label='上证指数', color='#A23B72', linewidth=1.2, alpha=0.8)
    
    ax1.set_title('MACD绿柱收缩策略(移动止盈+背离) vs 上证指数', fontsize=14, fontweight='bold')
    ax1.set_ylabel('净值', fontsize=11)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    st_metrics = calculate_metrics([{'date': str(r['date'].date()), 'equity': r['equity']} for _, r in strategy_df.iterrows()])
    bm_metrics = None
    if benchmark_df is not None and len(benchmark_df) > 0:
        bm_metrics = calculate_metrics([{'date': str(r['date'].date()), 'equity': r['equity']} for _, r in benchmark_df.iterrows()])
    
    textstr = f'策略收益: {st_metrics["totalReturn"]:.1f}%\n'
    textstr += f'年化收益: {st_metrics["annualizedReturn"]:.1f}%\n'
    textstr += f'最大回撤: {st_metrics["maxDrawdown"]:.1f}%\n'
    textstr += f'夏普比率: {st_metrics["sharpeRatio"]:.2f}'
    
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=9,
             verticalalignment='top', bbox=props)
    
    if bm_metrics:
        textstr2 = f'基准收益: {bm_metrics["totalReturn"]:.1f}%\n'
        textstr2 += f'年化收益: {bm_metrics["annualizedReturn"]:.1f}%\n'
        textstr2 += f'最大回撤: {bm_metrics["maxDrawdown"]:.1f}%\n'
        textstr2 += f'夏普比率: {bm_metrics["sharpeRatio"]:.2f}'
        
        ax1.text(0.15, 0.98, textstr2, transform=ax1.transAxes, fontsize=9,
                 verticalalignment='top', bbox=props)
    
    ax2 = axes[1]
    equity_values = strategy_df['equity'].values
    peak = np.maximum.accumulate(equity_values)
    drawdown = (peak - equity_values) / peak * 100
    ax2.fill_between(strategy_df['date'], 0, -drawdown, color='#E74C3C', alpha=0.5)
    ax2.set_ylabel('回撤 (%)', fontsize=11)
    ax2.set_title('策略回撤', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax3 = axes[2]
    if benchmark_df is not None and len(benchmark_df) > 0:
        merged = pd.merge_asof(
            strategy_df[['date', 'nav']].sort_values('date'),
            benchmark_df[['date', 'nav']].sort_values('date'),
            on='date',
            suffixes=('_st', '_bm')
        )
        merged['excess'] = (merged['nav_st'] - merged['nav_bm']) * 100
        ax3.fill_between(merged['date'], 0, merged['excess'], where=merged['excess'] >= 0, color='#27AE60', alpha=0.5, label='超额收益')
        ax3.fill_between(merged['date'], 0, merged['excess'], where=merged['excess'] < 0, color='#E74C3C', alpha=0.5, label='跑输基准')
        ax3.set_ylabel('超额收益 (%)', fontsize=11)
        ax3.set_title('相对上证指数超额收益', fontsize=12)
        ax3.legend(loc='upper left', fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n回测曲线图已保存: {output_path}")
    
    plt.close()


def main():
    print("=" * 70)
    print("MACD绿柱收缩策略(优化版) - 回测报告")
    print("=" * 70)
    
    print("\n策略参数：")
    print("  - 买点: MACD绿柱连续4根收缩(凹函数)")
    print("  - 卖点: 移动止盈(3%触发,回撤2%止盈) + 背离信号")
    print("  - 最大持仓: 10天")
    print("  - 仓位管理: 最多持有5只股票，每只18%仓位，总仓位90%")
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    print("\n运行策略回测...")
    equity_curve, all_trades = run_backtest(data, start_date, end_date)
    print(f"权益曲线数据点: {len(equity_curve)}")
    print(f"总交易次数: {len(all_trades)}")
    
    print("\n加载基准数据...")
    benchmark_sh = load_benchmark_from_arcticdb(start_date, end_date, symbol='000001.SH')
    benchmark_zz1000 = load_benchmark_from_arcticdb(start_date, end_date, symbol='000852.SH')
    
    if benchmark_sh:
        print(f"上证指数数据点数: {len(benchmark_sh)}")
    if benchmark_zz1000:
        print(f"中证1000数据点数: {len(benchmark_zz1000)}")
    
    print("\n计算策略指标...")
    st_metrics = calculate_metrics(equity_curve)
    bm_sh_metrics = calculate_metrics(benchmark_sh) if benchmark_sh else {}
    bm_zz1000_metrics = calculate_metrics(benchmark_zz1000) if benchmark_zz1000 else {}
    trade_metrics = calculate_trade_metrics(all_trades)
    
    print("\n" + "=" * 70)
    print("策略指标汇总")
    print("=" * 70)
    
    print(f"\n{'指标':^15} {'策略':^12} {'上证指数':^12} {'中证1000':^12} {'超额(上证)':^12} {'超额(中证1000)':^12}")
    print("-" * 85)
    
    def fmt(val, suffix='%'):
        if val is None:
            return '-'
        if isinstance(val, (int, float)) and val == 0:
            return '-'
        return f"{val:.2f}{suffix}"
    
    st_ret = st_metrics.get('totalReturn', 0)
    sh_ret = bm_sh_metrics.get('totalReturn', 0) if bm_sh_metrics else 0
    zz_ret = bm_zz1000_metrics.get('totalReturn', 0) if bm_zz1000_metrics else 0
    
    st_ann = st_metrics.get('annualizedReturn', 0)
    sh_ann = bm_sh_metrics.get('annualizedReturn', 0) if bm_sh_metrics else 0
    zz_ann = bm_zz1000_metrics.get('annualizedReturn', 0) if bm_zz1000_metrics else 0
    
    print(f"{'总收益率':^15} {fmt(st_metrics.get('totalReturn')):^12} {fmt(bm_sh_metrics.get('totalReturn')):^12} {fmt(bm_zz1000_metrics.get('totalReturn')):^12} {fmt(st_ret - sh_ret):^12} {fmt(st_ret - zz_ret):^12}")
    print(f"{'年化收益率':^15} {fmt(st_metrics.get('annualizedReturn')):^12} {fmt(bm_sh_metrics.get('annualizedReturn')):^12} {fmt(bm_zz1000_metrics.get('annualizedReturn')):^12} {fmt(st_ann - sh_ann):^12} {fmt(st_ann - zz_ann):^12}")
    print(f"{'最大回撤':^15} {fmt(st_metrics.get('maxDrawdown')):^12} {fmt(bm_sh_metrics.get('maxDrawdown')):^12} {fmt(bm_zz1000_metrics.get('maxDrawdown')):^12} {'-':^12} {'-':^12}")
    print(f"{'夏普比率':^15} {fmt(st_metrics.get('sharpeRatio'), suffix=''):^12} {fmt(bm_sh_metrics.get('sharpeRatio'), suffix=''):^12} {fmt(bm_zz1000_metrics.get('sharpeRatio'), suffix=''):^12} {'-':^12} {'-':^12}")
    print(f"{'年化波动率':^15} {fmt(st_metrics.get('volatility')):^12} {fmt(bm_sh_metrics.get('volatility')):^12} {fmt(bm_zz1000_metrics.get('volatility')):^12} {'-':^12} {'-':^12}")
    
    print("\n" + "-" * 85)
    print(f"{'交易统计':^20}")
    print("-" * 85)
    print(f"{'总交易次数':^20} {trade_metrics['totalTrades']:^15}")
    print(f"{'胜率':^20} {fmt(trade_metrics['winRate']):^15}")
    print(f"{'盈亏比':^20} {trade_metrics['profitFactor']:^15.2f}")
    print(f"{'平均收益':^20} {fmt(trade_metrics['avgReturn']):^15}")
    
    print("\n" + "=" * 70)
    print("生成回测曲线图")
    print("=" * 70)
    
    output_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/backtest_curve_optimized.png"
    plot_backtest_curve_with_multi_benchmark(equity_curve, benchmark_sh, benchmark_zz1000, output_path)
    
    print("\n" + "=" * 70)
    print("回测完成")
    print("=" * 70)
    
    print(f"\n最终结果：")
    print(f"  初始资金: 100,000")
    print(f"  最终资金: {equity_curve[-1]['equity']:,.0f}")
    print(f"  策略总收益: {(equity_curve[-1]['equity'] - 100000) / 100000 * 100:.1f}%")
    
    if benchmark_sh:
        sh_return = (benchmark_sh[-1]['equity'] - 100000) / 100000 * 100
        print(f"  上证指数收益: {sh_return:.1f}%")
        print(f"  超额收益(上证): {(equity_curve[-1]['equity'] - 100000) / 100000 * 100 - sh_return:.1f}%")
    
    if benchmark_zz1000:
        zz_return = (benchmark_zz1000[-1]['equity'] - 100000) / 100000 * 100
        print(f"  中证1000收益: {zz_return:.1f}%")
        print(f"  超额收益(中证1000): {(equity_curve[-1]['equity'] - 100000) / 100000 * 100 - zz_return:.1f}%")
    
    print_trade_summary(all_trades)
    
    trade_csv_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/trade_records.csv"
    export_trade_records(all_trades, trade_csv_path)


def plot_backtest_curve_with_multi_benchmark(equity_curve: list, benchmark_sh: list, benchmark_zz1000: list, output_path: str):
    """绘制回测曲线图 - 多基准对比"""
    
    strategy_df = pd.DataFrame(equity_curve)
    strategy_df['date'] = pd.to_datetime(strategy_df['date'])
    strategy_df = strategy_df.sort_values('date')
    
    benchmark_sh_df = None
    if benchmark_sh:
        benchmark_sh_df = pd.DataFrame(benchmark_sh)
        benchmark_sh_df['date'] = pd.to_datetime(benchmark_sh_df['date'])
        benchmark_sh_df = benchmark_sh_df.sort_values('date')
    
    benchmark_zz_df = None
    if benchmark_zz1000:
        benchmark_zz_df = pd.DataFrame(benchmark_zz1000)
        benchmark_zz_df['date'] = pd.to_datetime(benchmark_zz_df['date'])
        benchmark_zz_df = benchmark_zz_df.sort_values('date')
    
    start_date = strategy_df['date'].min()
    end_date = strategy_df['date'].max()
    
    if benchmark_sh_df is not None:
        start_date = max(start_date, benchmark_sh_df['date'].min())
        end_date = min(end_date, benchmark_sh_df['date'].max())
    if benchmark_zz_df is not None:
        start_date = max(start_date, benchmark_zz_df['date'].min())
        end_date = min(end_date, benchmark_zz_df['date'].max())
    
    strategy_df = strategy_df[(strategy_df['date'] >= start_date) & (strategy_df['date'] <= end_date)].copy()
    if benchmark_sh_df is not None:
        benchmark_sh_df = benchmark_sh_df[(benchmark_sh_df['date'] >= start_date) & (benchmark_sh_df['date'] <= end_date)].copy()
    if benchmark_zz_df is not None:
        benchmark_zz_df = benchmark_zz_df[(benchmark_zz_df['date'] >= start_date) & (benchmark_zz_df['date'] <= end_date)].copy()
    
    if len(strategy_df) == 0:
        print("警告: 日期对齐后策略数据为空")
        return
    
    strategy_df['nav'] = strategy_df['equity'] / strategy_df['equity'].iloc[0]
    if benchmark_sh_df is not None and len(benchmark_sh_df) > 0:
        benchmark_sh_df['nav'] = benchmark_sh_df['equity'] / benchmark_sh_df['equity'].iloc[0]
    if benchmark_zz_df is not None and len(benchmark_zz_df) > 0:
        benchmark_zz_df['nav'] = benchmark_zz_df['equity'] / benchmark_zz_df['equity'].iloc[0]
    
    print(f"\n日期对齐后:")
    print(f"  策略日期范围: {strategy_df['date'].min().date()} 到 {strategy_df['date'].max().date()}")
    print(f"  策略数据点: {len(strategy_df)}")
    if benchmark_sh_df is not None:
        print(f"  上证指数数据点: {len(benchmark_sh_df)}")
    if benchmark_zz_df is not None:
        print(f"  中证1000数据点: {len(benchmark_zz_df)}")
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1, 1]})
    
    ax1 = axes[0]
    ax1.plot(strategy_df['date'], strategy_df['nav'], label='MACD绿柱收缩策略', color='#2E86AB', linewidth=1.5)
    
    if benchmark_sh_df is not None and len(benchmark_sh_df) > 0:
        ax1.plot(benchmark_sh_df['date'], benchmark_sh_df['nav'], label='上证指数', color='#A23B72', linewidth=1.2, alpha=0.8)
    
    if benchmark_zz_df is not None and len(benchmark_zz_df) > 0:
        ax1.plot(benchmark_zz_df['date'], benchmark_zz_df['nav'], label='中证1000', color='#F18F01', linewidth=1.2, alpha=0.8)
    
    ax1.set_title('MACD绿柱收缩策略(移动止盈+背离) vs 基准指数', fontsize=14, fontweight='bold')
    ax1.set_ylabel('净值', fontsize=11)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    st_metrics = calculate_metrics([{'date': str(r['date'].date()), 'equity': r['equity']} for _, r in strategy_df.iterrows()])
    bm_sh_metrics = None
    bm_zz_metrics = None
    if benchmark_sh_df is not None and len(benchmark_sh_df) > 0:
        bm_sh_metrics = calculate_metrics([{'date': str(r['date'].date()), 'equity': r['equity']} for _, r in benchmark_sh_df.iterrows()])
    if benchmark_zz_df is not None and len(benchmark_zz_df) > 0:
        bm_zz_metrics = calculate_metrics([{'date': str(r['date'].date()), 'equity': r['equity']} for _, r in benchmark_zz_df.iterrows()])
    
    textstr = f'策略收益: {st_metrics["totalReturn"]:.1f}%\n'
    textstr += f'年化收益: {st_metrics["annualizedReturn"]:.1f}%\n'
    textstr += f'最大回撤: {st_metrics["maxDrawdown"]:.1f}%\n'
    textstr += f'夏普比率: {st_metrics["sharpeRatio"]:.2f}'
    
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=9,
             verticalalignment='top', bbox=props)
    
    if bm_sh_metrics:
        textstr2 = f'上证指数: {bm_sh_metrics["totalReturn"]:.1f}%\n'
        textstr2 += f'年化: {bm_sh_metrics["annualizedReturn"]:.1f}%\n'
        textstr2 += f'回撤: {bm_sh_metrics["maxDrawdown"]:.1f}%'
        ax1.text(0.15, 0.98, textstr2, transform=ax1.transAxes, fontsize=9,
                 verticalalignment='top', bbox=props)
    
    if bm_zz_metrics:
        textstr3 = f'中证1000: {bm_zz_metrics["totalReturn"]:.1f}%\n'
        textstr3 += f'年化: {bm_zz_metrics["annualizedReturn"]:.1f}%\n'
        textstr3 += f'回撤: {bm_zz_metrics["maxDrawdown"]:.1f}%'
        ax1.text(0.28, 0.98, textstr3, transform=ax1.transAxes, fontsize=9,
                 verticalalignment='top', bbox=props)
    
    ax2 = axes[1]
    equity_values = strategy_df['equity'].values
    peak = np.maximum.accumulate(equity_values)
    drawdown = (peak - equity_values) / peak * 100
    ax2.fill_between(strategy_df['date'], 0, -drawdown, color='#E74C3C', alpha=0.5)
    ax2.set_ylabel('回撤 (%)', fontsize=11)
    ax2.set_title('策略回撤', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax3 = axes[2]
    if benchmark_sh_df is not None and len(benchmark_sh_df) > 0:
        merged = pd.merge_asof(
            strategy_df[['date', 'nav']].sort_values('date'),
            benchmark_sh_df[['date', 'nav']].sort_values('date'),
            on='date',
            suffixes=('_st', '_bm')
        )
        merged['excess'] = (merged['nav_st'] - merged['nav_bm']) * 100
        ax3.fill_between(merged['date'], 0, merged['excess'], where=merged['excess'] >= 0, color='#27AE60', alpha=0.5, label='超额收益(上证)')
        ax3.fill_between(merged['date'], 0, merged['excess'], where=merged['excess'] < 0, color='#E74C3C', alpha=0.5, label='跑输上证')
        ax3.set_ylabel('超额收益 (%)', fontsize=11)
        ax3.set_title('相对上证指数超额收益', fontsize=12)
        ax3.legend(loc='upper left', fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n回测曲线图已保存: {output_path}")
    
    plt.close()


if __name__ == "__main__":
    main()
