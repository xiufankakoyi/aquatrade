"""
策略评估与固化 - 前三名策略对比指数

功能：
1. 生成前三名策略与上证指数累计收益对比图
2. 计算最大回撤、夏普比率等风险指标
3. 保存最优策略配置到JSON文件
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
from typing import Dict, List, Tuple
from dataclasses import dataclass
from itertools import product
import json
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class ConditionConfig:
    """条件配置"""
    stock_type: str
    vs_filter: str
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
    
    def to_dict(self) -> dict:
        return {
            'stock_type': self.stock_type,
            'vs_filter': self.vs_filter,
            'volume_filter': self.volume_filter,
            'rsi_filter': self.rsi_filter,
            'ma_filter': self.ma_filter,
        }


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
def calc_volatility_strength(close: np.ndarray, high: np.ndarray, low: np.ndarray, idx: int) -> float:
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
    import lancedb
    import polars as pl
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print(f"加载数据: {start_date} - {end_date}")
    
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        stock_code = row['stock_code']
        if stock_code not in daily_data:
            daily_data[stock_code] = {'dates': [], 'close': [], 'high': [], 'low': [], 'open': [], 'volume': []}
        daily_data[stock_code]['dates'].append(str(row['trade_date']))
        daily_data[stock_code]['close'].append(row['close'])
        daily_data[stock_code]['high'].append(row.get('high', row['close']))
        daily_data[stock_code]['low'].append(row.get('low', row['close']))
        daily_data[stock_code]['open'].append(row.get('open', row['close']))
        daily_data[stock_code]['volume'].append(row['volume'])
    
    for stock_code in daily_data:
        dates_arr = np.array(daily_data[stock_code]['dates'])
        sorted_idx = np.argsort(dates_arr)
        for key in ['dates', 'close', 'high', 'low', 'open', 'volume']:
            arr = np.array(daily_data[stock_code][key])
            if key != 'dates':
                arr = arr.astype(np.float64)
            daily_data[stock_code][key] = arr[sorted_idx]
    
    print(f"  股票数: {len(daily_data)}")
    return daily_data


def load_benchmark_from_arcticdb(start_date: str, end_date: str, initial_capital: float = 100000, symbol: str = '000001.SH'):
    """从ArcticDB加载指数基准数据"""
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
        return None


def check_conditions(stock_code: str, close: np.ndarray, high: np.ndarray, low: np.ndarray,
                     open_price: np.ndarray, volume: np.ndarray, signal_idx: int, config: ConditionConfig) -> bool:
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


def run_backtest_for_year(daily_data: Dict, test_year: int, config: ConditionConfig) -> Dict:
    year_start = f"{test_year}-01-01"
    year_end = f"{test_year}-12-31"
    
    all_trades = []
    
    for stock_code in sorted(daily_data.keys()):
        d = daily_data[stock_code]
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
        
        close = close[mask].astype(np.float64)
        high = high[mask].astype(np.float64)
        low = low[mask].astype(np.float64)
        open_price = open_price[mask].astype(np.float64)
        volume = volume[mask].astype(np.float64)
        dates = dates[mask]
        hist = hist[mask].astype(np.float64)
        rsi = rsi[mask].astype(np.float64)
        peaks = peaks[mask]
        signals = signals[mask]
        
        if len(close) < 50:
            continue
        
        for i in range(len(signals) - 1):
            if signals[i]:
                buy_date_idx = i + 1
                if buy_date_idx >= len(close):
                    continue
                
                if not check_conditions(stock_code, close, high, low, open_price, volume, i, config):
                    continue
                
                buy_price = close[buy_date_idx]
                sell_price = buy_price
                peak_price = buy_price
                triggered_trailing = False
                hold_days = 0
                
                for hold_day in range(10):
                    check_idx = buy_date_idx + hold_day
                    if check_idx >= len(close):
                        check_idx = len(close) - 1
                        sell_price = close[check_idx]
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
                        hold_days = hold_day + 1
                        break
                    
                    if triggered_trailing:
                        drawdown = (peak_price - close[check_idx]) / peak_price
                        if drawdown >= 0.02:
                            sell_price = close[check_idx]
                            hold_days = hold_day + 1
                            break
                    
                    if hold_day == 9:
                        sell_price = close[check_idx]
                        hold_days = 10
                
                ret = (sell_price - buy_price) / buy_price
                all_trades.append({'stock_code': stock_code, 'buy_date': str(dates[buy_date_idx]), 'return': ret})
    
    if not all_trades:
        return {'return': 0, 'trades': 0, 'win_rate': 0, 'profit_factor': 0}
    
    returns = [t['return'] for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    total_return = sum(returns)
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
    
    return {'return': total_return * 100, 'trades': len(all_trades), 'win_rate': win_rate, 'profit_factor': profit_factor}


def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """计算最大回撤"""
    peak = equity_curve[0]
    max_dd = 0
    
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    
    return max_dd * 100


def calculate_sharpe_ratio(returns: List[float], rf: float = 0.02) -> float:
    """计算夏普比率"""
    if len(returns) < 2:
        return 0
    
    returns_arr = np.array(returns)
    excess_returns = returns_arr - rf / 252
    
    if np.std(excess_returns) == 0:
        return 0
    
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)


def main():
    print("=" * 70)
    print("策略评估与固化 - 前三名策略对比指数")
    print("=" * 70)
    
    start_date = "2015-01-01"
    end_date = "2025-12-31"
    test_years = list(range(2015, 2026))
    
    daily_data = load_data(start_date, end_date)
    
    top_configs = [
        ConditionConfig('all', 'vs_05', False, False, False),
        ConditionConfig('all', 'vs_05', False, True, False),
        ConditionConfig('all', 'vs_05', True, False, False),
    ]
    
    print("\n" + "=" * 70)
    print("前三名策略条件")
    print("=" * 70)
    for i, config in enumerate(top_configs):
        print(f"\n第{i+1}名: {config.name()}")
    
    all_results = []
    for config in top_configs:
        yearly_results = []
        for year in test_years:
            result = run_backtest_for_year(daily_data, year, config)
            yearly_results.append({'year': year, **result})
        all_results.append({'config': config, 'yearly_results': yearly_results})
    
    print("\n加载上证指数数据...")
    benchmark_sh = load_benchmark_from_arcticdb(start_date, end_date, symbol='000001.SH')
    
    if benchmark_sh:
        print(f"  上证指数: {len(benchmark_sh)} 条")
    
    print("\n" + "=" * 70)
    print("计算累计收益和风险指标")
    print("=" * 70)
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    colors = ['#2E86AB', '#E74C3C', '#27AE60']
    labels = ['策略1: VS>=0.5', '策略2: VS>=0.5+RSI', '策略3: VS>=0.5+成交量']
    
    metrics_table = []
    
    for idx, result in enumerate(all_results):
        yearly_results = result['yearly_results']
        config = result['config']
        
        cumulative_return = 0
        curve_data = []
        yearly_returns = []
        
        for yr in yearly_results:
            cumulative_return += yr['return']
            curve_data.append({'year': yr['year'], 'cumulative_return': cumulative_return})
            yearly_returns.append(yr['return'])
        
        df = pd.DataFrame(curve_data)
        
        ax1 = axes[0]
        ax1.plot(df['year'], df['cumulative_return'], label=labels[idx], color=colors[idx], linewidth=2, marker='o')
        
        ax2 = axes[1]
        ax2.bar([y + idx * 0.25 for y in df['year']], yearly_returns, width=0.25, label=labels[idx], color=colors[idx], alpha=0.7)
        
        max_dd = calculate_max_drawdown(df['cumulative_return'].tolist())
        sharpe = calculate_sharpe([r/100 for r in yearly_returns])
        total_return = cumulative_return
        avg_return = np.mean(yearly_returns)
        return_std = np.std(yearly_returns)
        
        metrics_table.append({
            'strategy': labels[idx],
            'total_return': total_return,
            'avg_return': avg_return,
            'return_std': return_std,
            'max_drawdown': max_dd,
            'sharpe': sharpe,
        })
    
    if benchmark_sh:
        bm_df = pd.DataFrame(benchmark_sh)
        bm_df['date'] = pd.to_datetime(bm_df['date'])
        bm_df['year'] = bm_df['date'].dt.year
        
        bm_yearly = []
        for year in test_years:
            year_data = bm_df[bm_df['year'] == year]
            if len(year_data) > 0:
                year_return = (year_data['equity'].iloc[-1] / year_data['equity'].iloc[0] - 1) * 100
                bm_yearly.append({'year': year, 'return': year_return})
        
        bm_df_yearly = pd.DataFrame(bm_yearly)
        
        if len(bm_df_yearly) > 0:
            bm_cumulative = 0
            bm_curve = []
            for _, row in bm_df_yearly.iterrows():
                bm_cumulative += row['return']
                bm_curve.append({'year': row['year'], 'cumulative_return': bm_cumulative})
            
            bm_curve_df = pd.DataFrame(bm_curve)
            
            axes[0].plot(bm_curve_df['year'], bm_curve_df['cumulative_return'], 
                        label='上证指数', color='#95A5A6', linewidth=2, linestyle='--', marker='s')
            
            axes[1].bar([y + 3 * 0.25 for y in bm_df_yearly['year']], bm_df_yearly['return'], 
                       width=0.25, label='上证指数', color='#95A5A6', alpha=0.7)
            
            bm_max_dd = calculate_max_drawdown(bm_curve_df['cumulative_return'].tolist())
            bm_sharpe = calculate_sharpe([r/100 for r in bm_df_yearly['return'].tolist()])
            bm_total = bm_cumulative
            
            metrics_table.append({
                'strategy': '上证指数',
                'total_return': bm_total,
                'avg_return': np.mean(bm_df_yearly['return']),
                'return_std': np.std(bm_df_yearly['return']),
                'max_drawdown': bm_max_dd,
                'sharpe': bm_sharpe,
            })
    
    axes[0].set_title('累计收益对比 (2015-2025)', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('年份', fontsize=11)
    axes[0].set_ylabel('累计收益 (%)', fontsize=11)
    axes[0].legend(loc='upper left', fontsize=9)
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    axes[1].set_title('年度收益对比', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('年份', fontsize=11)
    axes[1].set_ylabel('年度收益 (%)', fontsize=11)
    axes[1].legend(loc='upper left', fontsize=9)
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    plt.tight_layout()
    
    output_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/top3_strategy_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存: {output_path}")
    plt.close()
    
    print("\n" + "=" * 70)
    print("风险指标对比")
    print("=" * 70)
    
    print(f"\n{'策略':^20} {'总收益%':^10} {'年均收益%':^10} {'收益波动':^10} {'最大回撤%':^10} {'夏普比率':^10}")
    print("-" * 75)
    for m in metrics_table:
        print(f"{m['strategy']:<20} {m['total_return']:>10.1f} {m['avg_return']:>10.1f} {m['return_std']:>10.1f} {m['max_drawdown']:>10.1f} {m['sharpe']:>10.2f}")
    
    best_config = top_configs[0]
    best_metrics = metrics_table[0]
    
    config_output = {
        'name': '最优策略配置',
        'description': '波动率强度>=0.5，无其他过滤条件',
        'conditions': best_config.to_dict(),
        'performance': {
            'total_return': best_metrics['total_return'],
            'avg_return': best_metrics['avg_return'],
            'max_drawdown': best_metrics['max_drawdown'],
            'sharpe_ratio': best_metrics['sharpe'],
        },
        'backtest_period': f"{test_years[0]}-{test_years[-1]}",
    }
    
    config_path = "C:/Users/Liu/Desktop/projects/aquatrade/data/optimal_strategy_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_output, f, ensure_ascii=False, indent=2)
    
    print(f"\n最优策略配置已保存: {config_path}")
    
    print("\n" + "=" * 70)
    print("完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
