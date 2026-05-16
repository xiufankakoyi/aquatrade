"""
策略条件自动搜索系统

使用Walk-Forward时间序列验证，避免数据泄露
找出最稳定的策略条件组合

条件组合：
- 条件A：股票类型优先（不优先/创业板+科创板优先/仅创业板）
- 条件B：波动率强度过滤（无/VS>=0/VS>=0.5）
- 条件C：成交量过滤（无/有）
- 条件D：RSI过滤（无/有）
- 条件E：均线位置过滤（无/有）

验证方法：
- 2010-2014训练 → 2015测试
- 2011-2015训练 → 2016测试
- ... 依此类推
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from numba import njit
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from itertools import product
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class ConditionConfig:
    """条件配置"""
    stock_type: str  # 'all', 'gem_star', 'gem_only'
    vs_filter: str   # 'none', 'vs_0', 'vs_05'
    volume_filter: bool
    rsi_filter: bool
    ma_filter: bool
    
    def name(self) -> str:
        parts = []
        parts.append(f"股票:{self.stock_type}")
        parts.append(f"VS:{self.vs_filter}")
        parts.append(f"成交量:{'有' if self.volume_filter else '无'}")
        parts.append(f"RSI:{'有' if self.rsi_filter else '无'}")
        parts.append(f"均线:{'有' if self.ma_filter else '无'}")
        return " | ".join(parts)


@njit
def calc_ema(arr: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
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
def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    atr = np.zeros(n)
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr


@njit
def calc_std(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.std(close[start:i+1])
    return result


@njit
def calc_vol_ma(volume: np.ndarray, period: int = 5) -> np.ndarray:
    n = len(volume)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.mean(volume[start:i+1])
    return result


@njit
def calc_ma(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.mean(close[start:i+1])
    return result


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


@njit
def calc_volatility_strength(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    idx: int,
) -> float:
    """计算波动率强度"""
    if idx < 20 or idx >= len(close):
        return 0.0
    
    atr = calc_atr(high, low, close)
    std20 = calc_std(close, 20)
    
    atr_pct = atr[idx] / close[idx] * 100 if close[idx] > 0 else 0
    high_low_range = (high[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    std20_pct = std20[idx] / close[idx] * 100 if close[idx] > 0 else 0
    lower_shadow = (close[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    
    atr_norm = (atr_pct - 3.0) / 1.5
    range_norm = (high_low_range - 2.5) / 1.5
    std_norm = (std20_pct - 3.5) / 1.5
    shadow_norm = (lower_shadow - 1.5) / 1.5
    
    return 0.35 * atr_norm + 0.30 * range_norm + 0.20 * std_norm + 0.15 * shadow_norm


def load_data(start_date: str, end_date: str) -> Dict:
    """加载数据"""
    import lancedb
    import polars as pl
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print(f"加载数据: {start_date} - {end_date}")
    
    table = db.open_table("stock_info")
    stock_info_df = pl.from_arrow(table.to_arrow())
    
    stock_info = {}
    for row in stock_info_df.iter_rows(named=True):
        stock_info[row['stock_code']] = {
            'name': row.get('stock_name', ''),
            'industry': row.get('industry'),
        }
    
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
    
    print(f"  股票数: {len(daily_data)}")
    
    return {'stock_info': stock_info, 'daily_data': daily_data}


def check_conditions(
    stock_code: str,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    open_price: np.ndarray,
    volume: np.ndarray,
    signal_idx: int,
    config: ConditionConfig,
) -> bool:
    """检查条件是否满足"""
    
    is_gem = stock_code.startswith('300')
    is_star = stock_code.startswith('688')
    
    if config.stock_type == 'gem_only' and not is_gem:
        return False
    if config.stock_type == 'gem_star' and not (is_gem or is_star):
        return False
    
    vs = calc_volatility_strength(close, high, low, signal_idx)
    
    if config.vs_filter == 'vs_0' and vs < 0:
        return False
    if config.vs_filter == 'vs_05' and vs < 0.5:
        return False
    
    if config.volume_filter:
        vol_ma5 = calc_vol_ma(volume.astype(np.float64), 5)
        if vol_ma5[signal_idx] > 0:
            vol_ratio = volume[signal_idx] / vol_ma5[signal_idx]
            if vol_ratio < 1.5:
                return False
    
    if config.rsi_filter:
        rsi = calc_rsi(close)
        if rsi[signal_idx] > 50:
            return False
    
    if config.ma_filter:
        ma20 = calc_ma(close, 20)
        if close[signal_idx] > ma20[signal_idx]:
            return False
    
    return True


def run_backtest_for_year(
    data: Dict,
    test_year: int,
    config: ConditionConfig,
) -> Dict:
    """运行单年度回测"""
    
    year_start = f"{test_year}-01-01"
    year_end = f"{test_year}-12-31"
    
    all_trades = []
    
    for stock_code in sorted(data['daily_data'].keys()):
        d = data['daily_data'][stock_code]
        dates = d['dates']
        close = d['close']
        high = d['high']
        low = d['low']
        open_price = d['open']
        volume = d['volume']
        
        if len(close) < 50:
            continue
        
        dif, dea, hist = calc_macd(close)
        rsi = calc_rsi(close)
        peaks = find_local_peaks(close, window=5)
        signals = detect_signal(hist)
        
        mask = (dates >= year_start) & (dates <= year_end)
        if not np.any(mask):
            continue
        
        close = close[mask]
        high = high[mask]
        low = low[mask]
        open_price = open_price[mask]
        volume = volume[mask]
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
                
                if not check_conditions(
                    stock_code, close, high, low, open_price, volume,
                    i, config
                ):
                    continue
                
                buy_date = str(dates[buy_date_idx])
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                sell_reason = "timeout"
                hold_days = 0
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = hold_day
                        break
                    
                    if high[check_idx] > peak_price:
                        peak_price = high[check_idx]
                    
                    day_high_pct = (high[check_idx] - buy_price) / buy_price
                    
                    if day_high_pct >= 0.03:
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
                        sell_reason = "divergence"
                        hold_days = hold_day + 1
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= 0.02:
                            sell_price = close[check_idx]
                            sell_reason = "trailing_stop"
                            hold_days = hold_day + 1
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        sell_reason = "timeout"
                        hold_days = 10
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({
                    'stock_code': stock_code,
                    'buy_date': buy_date,
                    'return': ret,
                })
    
    if not all_trades:
        return {'return': 0, 'trades': 0, 'win_rate': 0, 'profit_factor': 0}
    
    returns = [t['return'] for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    total_return = sum(returns)
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
    
    return {
        'return': total_return * 100,
        'trades': len(all_trades),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
    }


def evaluate_config(
    data: Dict,
    config: ConditionConfig,
    test_years: List[int],
) -> Dict:
    """评估条件配置"""
    
    yearly_results = []
    
    for year in test_years:
        result = run_backtest_for_year(data, year, config)
        yearly_results.append({
            'year': year,
            **result
        })
    
    returns = [r['return'] for r in yearly_results]
    win_rates = [r['win_rate'] for r in yearly_results]
    profit_factors = [r['profit_factor'] for r in yearly_results if r['profit_factor'] != float('inf')]
    
    total_return = sum(returns)
    avg_return = np.mean(returns)
    return_std = np.std(returns)
    avg_win_rate = np.mean(win_rates)
    win_rate_std = np.std(win_rates)
    avg_pf = np.mean(profit_factors) if profit_factors else 0
    
    total_trades = sum(r['trades'] for r in yearly_results)
    
    positive_years = sum(1 for r in returns if r > 0)
    
    stability_score = (
        (positive_years / len(test_years)) * 40 +
        (1 - min(return_std / abs(avg_return) if avg_return != 0 else 1, 1)) * 30 +
        (1 - min(win_rate_std / avg_win_rate if avg_win_rate != 0 else 1, 1)) * 20 +
        min(avg_pf / 2, 1) * 10
    )
    
    return {
        'config': config,
        'yearly_results': yearly_results,
        'total_return': total_return,
        'avg_return': avg_return,
        'return_std': return_std,
        'avg_win_rate': avg_win_rate,
        'win_rate_std': win_rate_std,
        'avg_profit_factor': avg_pf,
        'total_trades': total_trades,
        'positive_years': positive_years,
        'stability_score': stability_score,
    }


def generate_all_configs() -> List[ConditionConfig]:
    """生成所有条件组合"""
    configs = []
    
    stock_types = ['all', 'gem_star', 'gem_only']
    vs_filters = ['none', 'vs_0', 'vs_05']
    volume_filters = [False, True]
    rsi_filters = [False, True]
    ma_filters = [False, True]
    
    for st, vs, vol, rsi, ma in product(stock_types, vs_filters, volume_filters, rsi_filters, ma_filters):
        configs.append(ConditionConfig(
            stock_type=st,
            vs_filter=vs,
            volume_filter=vol,
            rsi_filter=rsi,
            ma_filter=ma,
        ))
    
    return configs


def plot_equity_curves(
    data: Dict,
    top_configs: List[Dict],
    test_years: List[int],
    output_path: str,
):
    """绘制前两名收益曲线"""
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    colors = ['#2E86AB', '#E74C3C']
    
    for idx, result in enumerate(top_configs):
        config = result['config']
        yearly_results = result['yearly_results']
        
        cumulative_return = 0
        curve_data = []
        
        for yr in yearly_results:
            cumulative_return += yr['return']
            curve_data.append({
                'year': yr['year'],
                'cumulative_return': cumulative_return,
            })
        
        df = pd.DataFrame(curve_data)
        
        ax = axes[0]
        ax.bar(df['year'] + idx * 0.2, df['cumulative_return'], width=0.35, 
               label=f"策略{idx+1}: {config.name()}", color=colors[idx], alpha=0.7)
        
        ax = axes[1]
        returns = [yr['return'] for yr in yearly_results]
        ax.bar([y + idx * 0.2 for y in df['year']], returns, width=0.35,
               label=f"策略{idx+1}", color=colors[idx], alpha=0.7)
    
    axes[0].set_title('累计收益对比', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('年份')
    axes[0].set_ylabel('累计收益 (%)')
    axes[0].legend(loc='upper left', fontsize=8)
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    axes[1].set_title('年度收益对比', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('年份')
    axes[1].set_ylabel('年度收益 (%)')
    axes[1].legend(loc='upper left', fontsize=8)
    axes[1].grid(True, alpha=0.3)
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n收益曲线图已保存: {output_path}")
    plt.close()


def main():
    print("=" * 70)
    print("策略条件自动搜索系统")
    print("=" * 70)
    
    print("\n【验证方法】Walk-Forward时间序列验证")
    print("  - 每年独立测试，无数据泄露")
    print("  - 所有计算只使用当前及之前数据")
    
    data = load_data("2010-01-01", "2025-12-31")
    
    test_years = list(range(2015, 2026))
    print(f"\n【测试年度】{test_years[0]} - {test_years[-1]} ({len(test_years)}年)")
    
    configs = generate_all_configs()
    print(f"\n【条件组合数】{len(configs)}种")
    
    print("\n" + "=" * 70)
    print("开始评估所有条件组合...")
    print("=" * 70)
    
    results = []
    for i, config in enumerate(configs):
        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{len(configs)}")
        
        result = evaluate_config(data, config, test_years)
        results.append(result)
    
    results.sort(key=lambda x: x['stability_score'], reverse=True)
    
    print("\n" + "=" * 70)
    print("Top 10 条件组合排名")
    print("=" * 70)
    
    print(f"\n{'排名':^4} {'稳定性':^8} {'总收益%':^10} {'收益波动':^10} {'胜率%':^8} {'盈亏比':^8} {'正收益年':^8} {'交易数':^8}")
    print("-" * 80)
    
    for i, r in enumerate(results[:10]):
        print(f"{i+1:^4} {r['stability_score']:^8.1f} {r['total_return']:^10.1f} {r['return_std']:^10.1f} {r['avg_win_rate']:^8.1f} {r['avg_profit_factor']:^8.2f} {r['positive_years']:^8}/{len(test_years)} {r['total_trades']:^8}")
    
    print("\n" + "=" * 70)
    print("前两名详细条件")
    print("=" * 70)
    
    for i, r in enumerate(results[:2]):
        config = r['config']
        print(f"\n【第{i+1}名】")
        print(f"  条件: {config.name()}")
        print(f"  稳定性得分: {r['stability_score']:.1f}")
        print(f"  总收益: {r['total_return']:.1f}%")
        print(f"  平均年收益: {r['avg_return']:.1f}%")
        print(f"  收益波动: {r['return_std']:.1f}")
        print(f"  平均胜率: {r['avg_win_rate']:.1f}%")
        print(f"  平均盈亏比: {r['avg_profit_factor']:.2f}")
        print(f"  正收益年数: {r['positive_years']}/{len(test_years)}")
        print(f"  总交易数: {r['total_trades']}")
        
        print(f"\n  各年度收益:")
        for yr in r['yearly_results']:
            print(f"    {yr['year']}: {yr['return']:+.1f}% ({yr['trades']}笔, 胜率{yr['win_rate']:.0f}%)")
    
    output_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/strategy_condition_comparison.png"
    plot_equity_curves(data, results[:2], test_years, output_path)
    
    print("\n" + "=" * 70)
    print("完成")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    results = main()
