"""
前三名策略回测对比指数 - 修正版
正确的仓位管理：每天最多持有5只股票，每只18%仓位
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
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


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
    return histogram


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
            rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    rsi[:period] = 50
    return rsi


@njit
def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
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
def detect_signal(bars: np.ndarray) -> np.ndarray:
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
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
    return 0.35 * (atr_pct - 3.0) / 1.5 + 0.30 * (high_low_range - 2.5) / 1.5 + 0.20 * (std20_pct - 3.5) / 1.5 + 0.15 * (lower_shadow - 1.5) / 1.5


def load_data(start_date: str, end_date: str):
    """
    加载数据（优化版）
    
    使用 LanceDBDataReader.read_as_dict() 替代 Python 循环，
    性能提升 100x+
    """
    import lancedb
    import polars as pl
    from datetime import datetime, timedelta
    from data_svc.storage.lancedb_reader import get_lancedb_reader
    
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    print(f"ST股票数: {len(st_stocks)}, 新股数(60天内): {len(new_stocks)}")
    
    filter_stocks = st_stocks | new_stocks
    
    reader = get_lancedb_reader()
    fields = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
    
    daily_data = reader.read_as_dict(
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        filter_stocks=filter_stocks,
    )
    
    for sc in daily_data:
        daily_data[sc]['dates'] = daily_data[sc].pop('trade_date')
    
    print(f"过滤后股票数: {len(daily_data)}")
    return daily_data


def load_benchmark(start_date: str, end_date: str, symbol: str = '000001.SH'):
    """从LanceDB加载指数数据"""
    try:
        import lancedb
        import polars as pl
        db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
        tables = db.list_tables()
        table_names = [t for t in tables.tables] if hasattr(tables, 'tables') else list(tables)
        if 'index_daily' not in table_names:
            print("LanceDB中没有index_daily表")
            return None
        table = db.open_table("index_daily")
        df = pl.from_arrow(table.to_arrow())
        df = df.filter(pl.col('symbol') == symbol)
        df = df.with_columns(pl.col('trade_date').cast(pl.Datetime).dt.strftime('%Y-%m-%d'))
        df = df.filter((pl.col('trade_date') >= start_date) & (pl.col('trade_date') <= end_date))
        df = df.sort('trade_date')
        if len(df) == 0:
            print(f"没有找到指数数据: {symbol}")
            return None
        first = df['close'][0]
        result = []
        for row in df.iter_rows(named=True):
            result.append({'date': row['trade_date'], 'nav': row['close'] / first})
        return result
    except Exception as e:
        print(f"加载指数失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_backtest(daily_data, start_date, end_date, config):
    """
    运行回测 - 正确的仓位管理
    每天最多持有5只股票，每只18%仓位
    按波动率强度排序选股
    """
    all_trades = []
    
    for sc in sorted(daily_data.keys()):
        d = daily_data[sc]
        dates, close = d['dates'], d['close']
        open_prices = d['open']
        high, low, volume = d['high'], d['low'], d['volume']
        
        if len(close) < 50:
            continue
        
        # 转换日期为字符串以便比较
        dates_str = np.array([str(d)[:10] for d in dates])
        mask = (dates_str >= start_date) & (dates_str <= end_date)
        if not np.any(mask):
            continue
        
        hist = calc_macd(close)
        rsi = calc_rsi(close)
        signals = detect_signal(hist)
        
        for i in range(len(signals) - 1):
            if not signals[i]:
                continue
            
            if dates_str[i] < start_date or dates_str[i] > end_date:
                continue
            
            buy_idx = i + 1
            if buy_idx >= len(close):
                continue
            
            vs = calc_volatility_strength(close, high, low, i)
            if config.get('vs_threshold') and vs < config['vs_threshold']:
                continue
            if config.get('rsi_filter') and rsi[i] > 50:
                continue
            if config.get('volume_filter'):
                vol_ma5 = calc_vol_ma(volume, 5)
                if vol_ma5[i] > 0 and volume[i] / vol_ma5[i] < 1.5:
                    continue
            
            buy_price = open_prices[buy_idx]
            peak_price = buy_price
            triggered = False
            sell_price = buy_price
            hold_days = 0
            
            for day in range(10):
                chk = buy_idx + day
                if chk >= len(close):
                    sell_price = close[-1]
                    hold_days = day
                    break
                if high[chk] > peak_price:
                    peak_price = high[chk]
                if (high[chk] - buy_price) / buy_price >= 0.03:
                    triggered = True
                if triggered and (peak_price - close[chk]) / peak_price >= 0.02:
                    sell_price = close[chk]
                    hold_days = day + 1
                    break
                sell_price = close[chk]
                hold_days = day + 1
            
            ret = (sell_price - buy_price) / buy_price
            sell_date = str(dates[min(buy_idx + hold_days, len(dates) - 1)])
            
            all_trades.append({
                'stock_code': sc,
                'buy_date': str(dates[buy_idx]),
                'sell_date': sell_date,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'return': ret,
                'vs': vs,
            })
    
    # 按买入日期分组，按VS排序选前5
    trades_by_buy_date = defaultdict(list)
    for t in all_trades:
        trades_by_buy_date[t['buy_date']].append(t)
    
    for date in trades_by_buy_date:
        trades_by_buy_date[date].sort(key=lambda x: x['vs'], reverse=True)
    
    # 模拟交易
    all_dates = set()
    for t in all_trades:
        all_dates.add(t['buy_date'])
        all_dates.add(t['sell_date'])
    all_dates = sorted(all_dates)
    
    initial_capital = 100000.0
    capital = initial_capital
    holdings = {}  # stock_code -> {'position_value': x, 'return': r, 'sell_date': d}
    equity_curve = []
    
    for date in all_dates:
        # 卖出
        for sc in list(holdings.keys()):
            h = holdings[sc]
            if h['sell_date'] == date:
                capital += h['position_value'] * (1 + h['return'])
                del holdings[sc]
        
        # 买入
        if date in trades_by_buy_date:
            for t in trades_by_buy_date[date]:
                if t['stock_code'] in holdings:
                    continue
                if len(holdings) < 5:
                    position_value = initial_capital * 0.18
                    capital -= position_value
                    holdings[t['stock_code']] = {
                        'position_value': position_value,
                        'return': t['return'],
                        'sell_date': t['sell_date'],
                    }
        
        equity_curve.append({'date': date, 'equity': capital + sum(h['position_value'] * (1 + h['return']) for h in holdings.values())})
    
    # 最后清仓
    for sc in holdings:
        capital += holdings[sc]['position_value'] * (1 + holdings[sc]['return'])
    
    final_equity = capital
    total_return = (final_equity - initial_capital) / initial_capital * 100
    
    return equity_curve, total_return, len(all_trades), all_trades


def main():
    print("=" * 60)
    print("策略2 vs 上证指数 (2015-2025)")
    print("=" * 60)
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    daily_data = load_data(start_date, end_date)
    
    config = {'name': '策略2: VS>=0.5+RSI<50', 'vs_threshold': 0.5, 'rsi_filter': True}
    
    print(f"\n运行回测: {config['name']}...")
    curve, total_ret, trades, trade_list = run_backtest(daily_data, start_date, end_date, config)
    print(f"  交易次数: {trades}, 总收益: {total_ret:.1f}%")
    
    # 输出2026年1月交易记录
    print("\n" + "=" * 60)
    print("2026年1月交易记录")
    print("=" * 60)
    trade_list_2026 = [t for t in trade_list if t['buy_date'].startswith('2026-01')]
    trade_list_2026.sort(key=lambda x: x['buy_date'])
    
    # 按日期排序输出买卖记录
    buy_records = []
    sell_records = []
    for t in trade_list_2026:
        buy_records.append({
            'date': t['buy_date'],
            'stock': t['stock_code'],
            'price': t['buy_price'],
            'action': 'BUY'
        })
        sell_records.append({
            'date': t['sell_date'],
            'stock': t['stock_code'],
            'price': t['sell_price'],
            'action': 'SELL'
        })
    
    all_records = buy_records + sell_records
    all_records.sort(key=lambda x: x['date'])
    
    for r in all_records[:30]:  # 只显示前30条
        print(f"{r['date']} {r['action']:4s} {r['stock']} @ {r['price']:.2f}")
    
    print("\n加载上证指数...")
    benchmark = load_benchmark(start_date, end_date, '000001.SH')
    bm_ret = (benchmark[-1]['nav'] - 1) * 100 if benchmark else 0
    print(f"  上证指数: {bm_ret:.1f}%")
    
    # 检查是否有交易记录
    if not curve or len(curve) == 0:
        print("\n⚠️ 没有交易记录，无法生成图表")
        print("\n" + "=" * 60)
        print("最终收益对比")
        print("=" * 60)
        print(f"  {config['name']}: {total_ret:.1f}% ({trades}笔)")
        print(f"  上证指数: {bm_ret:.1f}%")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    df = pd.DataFrame(curve)
    if 'date' not in df.columns or len(df) == 0:
        print("\n⚠️ 没有交易记录，无法生成图表")
        plt.close()
        return
    
    df['date'] = pd.to_datetime(df['date'])
    df['nav'] = df['equity'] / 100000
    ax.plot(df['date'], df['nav'], label=f"{config['name']} ({total_ret:.1f}%)", color='#2E86AB', linewidth=2)
    
    if benchmark:
        bm_df = pd.DataFrame(benchmark)
        bm_df['date'] = pd.to_datetime(bm_df['date'])
        ax.plot(bm_df['date'], bm_df['nav'], label=f'上证指数 ({bm_ret:.1f}%)', color='#E74C3C', linewidth=2, linestyle='--')
    
    ax.set_title('策略2 vs 上证指数 (2015-2025)', fontsize=14, fontweight='bold')
    ax.set_xlabel('日期', fontsize=11)
    ax.set_ylabel('净值 (初始=1)', fontsize=11)
    ax.legend(loc='upper left', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    plt.xticks(rotation=45)
    
    output = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/strategy2_vs_shanghai.png"
    plt.savefig(output, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存: {output}")
    plt.close()
    
    print("\n" + "=" * 60)
    print("最终收益对比")
    print("=" * 60)
    print(f"  {config['name']}: {total_ret:.1f}% ({trades}笔)")
    print(f"  上证指数: {bm_ret:.1f}%")
    print(f"  超额收益: {total_ret - bm_ret:.1f}%")


if __name__ == "__main__":
    main()
