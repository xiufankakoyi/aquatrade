"""
前三名策略回测 - 修复版（防未来函数）

修复内容：
1. 信号生成只能基于历史数据（截止到昨日收盘）
2. 买入使用次日开盘价（T+1）
3. 卖出决策基于昨日收盘状态，今日开盘执行
4. 禁止使用high/low/close进行盘中决策
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

from core.backtest.lookahead_safe_engine import (
    LookaheadSafeBacktestEngine,
    BacktestConfig,
    validate_no_lookahead
)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


# =============================================================================
# 指标计算函数（Numba加速）
# =============================================================================

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
    """检测MACD柱状图信号"""
    n = len(bars)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = bars[i-3], bars[i-2], bars[i-1], bars[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                signals[i] = True
    return signals


@njit
def calc_volatility_strength(close: np.ndarray, high: np.ndarray, low: np.ndarray, idx: int) -> float:
    """计算波动率强度"""
    if idx < 20 or idx >= len(close):
        return 0.0
    atr = calc_atr(high, low, close)
    std20 = calc_std(close, 20)
    atr_pct = atr[idx] / close[idx] * 100 if close[idx] > 0 else 0
    high_low_range = (high[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    std20_pct = std20[idx] / close[idx] * 100 if close[idx] > 0 else 0
    lower_shadow = (close[idx] - low[idx]) / close[idx-1] * 100 if idx >= 1 and close[idx-1] > 0 else 0
    return 0.35 * (atr_pct - 3.0) / 1.5 + 0.30 * (high_low_range - 2.5) / 1.5 + 0.20 * (std20_pct - 3.5) / 1.5 + 0.15 * (lower_shadow - 1.5) / 1.5


# =============================================================================
# 信号生成器（防未来函数版本）
# =============================================================================

def create_signal_generator(config: dict):
    """
    创建信号生成器
    
    重要：信号生成器只能使用available_data中的数据
    这些数据截止到昨日收盘，不包含今天的任何信息
    """
    
    def signal_generator(available_data: dict, current_date: str, current_positions: dict) -> dict:
        """
        生成买入信号
        
        Args:
            available_data: 可用的历史数据（截止到昨日收盘）
            current_date: 当前日期（今天）
            current_positions: 当前持仓
            
        Returns:
            信号字典 {stock_code: {'reason': str}}
        """
        # 验证数据不包含未来信息（调试用）
        # validate_no_lookahead(available_data, current_date)
        
        signals = {}
        
        for sc, data in available_data.items():
            # 数据长度检查
            if len(data['close']) < 50:
                continue
            
            close = data['close']
            high = data['high']
            low = data['low']
            volume = data['volume']
            
            # 计算指标（基于历史数据）
            hist = calc_macd(close)
            rsi = calc_rsi(close)
            signal_mask = detect_signal(hist)
            
            # 检查最后一个交易日是否有信号
            if not signal_mask[-1]:
                continue
            
            # 获取信号日的索引
            signal_idx = len(close) - 1
            
            # 计算波动率强度
            vs = calc_volatility_strength(close, high, low, signal_idx)
            
            # 应用过滤条件
            if config.get('vs_threshold') and vs < config['vs_threshold']:
                continue
            
            if config.get('rsi_filter') and rsi[signal_idx] > 50:
                continue
            
            if config.get('volume_filter'):
                vol_ma5 = calc_vol_ma(volume, 5)
                if vol_ma5[signal_idx] > 0 and volume[signal_idx] / vol_ma5[signal_idx] < 1.5:
                    continue
            
            # 生成信号（将在明天开盘执行买入）
            signals[sc] = {
                'vs': vs,
                'rsi': rsi[signal_idx],
                'reason': f"macd_signal_vs{vs:.2f}"
            }
        
        # 按VS排序，只保留前5只
        sorted_signals = sorted(signals.items(), key=lambda x: x[1]['vs'], reverse=True)
        
        # 考虑当前持仓数量
        max_new_positions = 5 - len(current_positions)
        
        result = {}
        for sc, sig in sorted_signals[:max_new_positions]:
            if sc not in current_positions:
                result[sc] = sig
        
        return result
    
    return signal_generator


# =============================================================================
# 数据加载函数
# =============================================================================

def load_data(start_date: str, end_date: str):
    """加载数据"""
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
    """加载指数数据"""
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


# =============================================================================
# 主函数
# =============================================================================

def main():
    print("=" * 60)
    print("前三名策略回测 - 防未来函数版本")
    print("=" * 60)
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    # 加载数据
    daily_data = load_data(start_date, end_date)
    
    # 配置
    config = {
        'name': '策略2: VS>=0.5+RSI<50',
        'vs_threshold': 0.5,
        'rsi_filter': True,
        'volume_filter': False
    }
    
    # 创建回测配置
    backtest_config = BacktestConfig(
        initial_capital=100000.0,
        max_positions=5,
        position_ratio=0.18,
        take_profit_pct=0.03,
        trailing_stop_pct=0.02,
        max_holding_days=10,
        commission_rate=0.0003,
        min_commission=5.0,
        sell_tax=0.001
    )
    
    # 创建引擎
    engine = LookaheadSafeBacktestEngine(backtest_config)
    
    # 创建信号生成器
    signal_gen = create_signal_generator(config)
    
    print(f"\n运行回测: {config['name']}...")
    
    # 运行回测
    result = engine.run_backtest(
        daily_data=daily_data,
        start_date=start_date,
        end_date=end_date,
        signal_generator=signal_gen,
        progress_callback=lambda p: print(f"进度: {p:.1f}%", end='\r') if p % 10 < 1 else None
    )
    
    print(f"\n  交易次数: {result['trade_count']}, 总收益: {result['total_return']:.1f}%")
    print(f"  最大回撤: {result['max_drawdown']:.1f}%")
    print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
    
    # 加载基准
    print("\n加载上证指数...")
    benchmark = load_benchmark(start_date, end_date, '000001.SH')
    bm_ret = (benchmark[-1]['nav'] - 1) * 100 if benchmark else 0
    print(f"  上证指数: {bm_ret:.1f}%")
    
    # 绘制图表
    if result['equity_curve']:
        fig, ax = plt.subplots(figsize=(14, 8))
        
        df = pd.DataFrame(result['equity_curve'])
        df['date'] = pd.to_datetime(df['date'])
        df['nav'] = df['equity'] / 100000
        ax.plot(df['date'], df['nav'], 
                label=f"{config['name']} ({result['total_return']:.1f}%)", 
                color='#2E86AB', linewidth=2)
        
        if benchmark:
            bm_df = pd.DataFrame(benchmark)
            bm_df['date'] = pd.to_datetime(bm_df['date'])
            ax.plot(bm_df['date'], bm_df['nav'], 
                    label=f'上证指数 ({bm_ret:.1f}%)', 
                    color='#E74C3C', linewidth=2, linestyle='--')
        
        ax.set_title('策略2 vs 上证指数 (防未来函数版本)', fontsize=14, fontweight='bold')
        ax.set_xlabel('日期', fontsize=11)
        ax.set_ylabel('净值 (初始=1)', fontsize=11)
        ax.legend(loc='upper left', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        output = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/strategy2_lookahead_safe.png"
        plt.savefig(output, dpi=150, bbox_inches='tight')
        print(f"\n图表已保存: {output}")
        plt.close()
    
    print("\n" + "=" * 60)
    print("最终收益对比")
    print("=" * 60)
    print(f"  {config['name']}: {result['total_return']:.1f}% ({result['trade_count']}笔)")
    print(f"  上证指数: {bm_ret:.1f}%")
    print(f"  超额收益: {result['total_return'] - bm_ret:.1f}%")
    
    # 输出最近的交易记录
    print("\n" + "=" * 60)
    print("最近交易记录")
    print("=" * 60)
    recent_trades = [t for t in result['trades'] if t.action == 'sell'][-10:]
    for t in recent_trades:
        print(f"{t.date} SELL {t.stock_code} @ {t.price:.2f} ({t.reason})")


if __name__ == "__main__":
    main()
