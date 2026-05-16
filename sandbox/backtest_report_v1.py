"""
导入指数数据并生成回测曲线图
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
                 position_per_stock: float = 0.02, max_total_position: float = 0.80,
                 take_profit_pct: float = 0.03, max_hold_days: int = 10):
    """运行回测"""
    
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
    equity_curve = []
    
    for date in all_dates:
        for stock_code in list(holdings.keys()):
            h = holdings[stock_code]
            if h['sell_date'] == date:
                profit = h['position_value'] * h['return']
                capital += profit
                del holdings[stock_code]
        
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
        
        equity_curve.append({'date': date, 'equity': capital})
    
    for stock_code in list(holdings.keys()):
        h = holdings[stock_code]
        profit = h['position_value'] * h['return']
        capital += profit
    
    return equity_curve


def load_benchmark_from_arcticdb(start_date: str, end_date: str, initial_capital: float = 100000):
    """从ArcticDB加载上证指数基准数据"""
    try:
        from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
        
        arctic = get_arctic_instance_for_library('market_data')
        
        if 'market_data' not in arctic.list_libraries():
            print("market_data库不存在")
            return None
        
        lib = arctic['market_data']
        
        if '000001.SH' not in lib.list_symbols():
            print("上证指数数据不存在")
            return None
        
        item = lib.read('000001.SH', date_range=(pd.Timestamp(start_date), pd.Timestamp(end_date)))
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
    ax1.plot(strategy_df['date'], strategy_df['nav'], label='MACD绿柱收缩策略', color='#2E86AB', linewidth=1.5)
    
    if benchmark_df is not None and len(benchmark_df) > 0:
        ax1.plot(benchmark_df['date'], benchmark_df['nav'], label='上证指数', color='#A23B72', linewidth=1.2, alpha=0.8)
    
    ax1.set_title('MACD绿柱收缩策略 vs 上证指数', fontsize=14, fontweight='bold')
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
    print("MACD绿柱收缩策略 - 回测报告")
    print("=" * 70)
    
    print("\n策略参数：")
    print("  - 止盈: 3%")
    print("  - 最大持仓: 10天")
    print("  - 单股仓位: 2%")
    print("  - 总仓位上限: 80%")
    
    data = get_cache()
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print(f"\n回测区间: {start_date} 至 {end_date}")
    
    print("\n运行策略回测...")
    equity_curve = run_backtest(data, start_date, end_date)
    print(f"权益曲线数据点: {len(equity_curve)}")
    
    print("\n加载上证指数基准数据...")
    benchmark_curve = load_benchmark_from_arcticdb(start_date, end_date)
    
    if benchmark_curve:
        print(f"基准数据点数: {len(benchmark_curve)}")
    else:
        print("无法加载基准数据")
    
    print("\n计算策略指标...")
    st_metrics = calculate_metrics(equity_curve)
    bm_metrics = calculate_metrics(benchmark_curve) if benchmark_curve else {}
    
    print("\n" + "=" * 70)
    print("策略指标汇总")
    print("=" * 70)
    
    print(f"\n{'指标':^20} {'策略':^15} {'基准(上证)':^15} {'超额':^15}")
    print("-" * 65)
    
    def fmt(val, suffix='%'):
        if val is None:
            return '-'
        if isinstance(val, (int, float)) and val == 0:
            return '-'
        return f"{val:.2f}{suffix}"
    
    print(f"{'总收益率':^20} {fmt(st_metrics.get('totalReturn')):^15} {fmt(bm_metrics.get('totalReturn')):^15} {fmt(st_metrics.get('totalReturn', 0) - bm_metrics.get('totalReturn', 0)) if bm_metrics else '-':^15}")
    print(f"{'年化收益率':^20} {fmt(st_metrics.get('annualizedReturn')):^15} {fmt(bm_metrics.get('annualizedReturn')):^15} {fmt(st_metrics.get('annualizedReturn', 0) - bm_metrics.get('annualizedReturn', 0)) if bm_metrics else '-':^15}")
    print(f"{'最大回撤':^20} {fmt(st_metrics.get('maxDrawdown')):^15} {fmt(bm_metrics.get('maxDrawdown')):^15} {'-':^15}")
    print(f"{'夏普比率':^20} {fmt(st_metrics.get('sharpeRatio'), suffix=''):^15} {fmt(bm_metrics.get('sharpeRatio'), suffix=''):^15} {fmt(st_metrics.get('sharpeRatio', 0) - bm_metrics.get('sharpeRatio', 0), suffix='') if bm_metrics else '-':^15}")
    print(f"{'年化波动率':^20} {fmt(st_metrics.get('volatility')):^15} {fmt(bm_metrics.get('volatility')):^15} {'-':^15}")
    
    print("\n" + "=" * 70)
    print("生成回测曲线图")
    print("=" * 70)
    
    output_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/backtest_curve.png"
    plot_backtest_curve(equity_curve, benchmark_curve, output_path)
    
    print("\n" + "=" * 70)
    print("回测完成")
    print("=" * 70)
    
    print(f"\n最终结果：")
    print(f"  初始资金: 100,000")
    print(f"  最终资金: {equity_curve[-1]['equity']:,.0f}")
    print(f"  总收益: {(equity_curve[-1]['equity'] - 100000) / 100000 * 100:.1f}%")
    
    if benchmark_curve:
        benchmark_return = (benchmark_curve[-1]['equity'] - 100000) / 100000 * 100
        print(f"  基准收益: {benchmark_return:.1f}%")


if __name__ == "__main__":
    main()
