"""
最优策略执行模块 - MACD绿柱收缩+波动率强度策略
从配置文件加载参数，执行选股和回测
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
import pandas as pd
from numba import njit
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import lancedb
import polars as pl


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
def detect_green_bar_contraction(histogram: np.ndarray) -> np.ndarray:
    n = len(histogram)
    signals = np.zeros(n, dtype=np.bool_)
    for i in range(3, n):
        b0, b1, b2, b3 = histogram[i-3], histogram[i-2], histogram[i-1], histogram[i]
        if b0 < 0 and b1 < 0 and b2 < 0 and b3 < 0:
            if abs(b0) > abs(b1) > abs(b2) > abs(b3) and b3 > -0.005:
                signals[i] = True
    return signals


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


class OptimalStrategy:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "data" / "strategy_optimal_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self._parse_config()
    
    def _parse_config(self):
        entry = self.config['signal_conditions']['entry']
        self.macd_fast = entry['macd']['fast_period']
        self.macd_slow = entry['macd']['slow_period']
        self.macd_signal = entry['macd']['signal_period']
        self.vs_threshold = entry['volatility_strength']['threshold']
        self.rsi_period = entry['rsi']['period']
        self.rsi_max = entry['rsi']['max_value']
        
        exit_cfg = self.config['signal_conditions']['exit']
        self.max_hold_days = exit_cfg['max_hold_days']
        self.trailing_trigger = exit_cfg['trailing_stop']['trigger_pct'] / 100
        self.trailing_drawdown = exit_cfg['trailing_stop']['drawdown_pct'] / 100
        
        pos = self.config['position_management']
        self.max_holdings = pos['max_holdings']
        self.position_size = pos['position_size_pct'] / 100
    
    def load_stock_data(self, start_date: str, end_date: str) -> Dict:
        db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
        table = db.open_table("daily_ohlcv")
        daily_df = pl.from_arrow(table.to_arrow())
        daily_data = {}
        for row in daily_df.iter_rows(named=True):
            sc = row['stock_code']
            if sc not in daily_data:
                daily_data[sc] = {'dates': [], 'close': [], 'high': [], 'low': [], 'volume': []}
            date_str = str(row['trade_date'])[:10]
            daily_data[sc]['dates'].append(date_str)
            daily_data[sc]['close'].append(row['close'])
            daily_data[sc]['high'].append(row.get('high', row['close']))
            daily_data[sc]['low'].append(row.get('low', row['close']))
            daily_data[sc]['volume'].append(row['volume'])
        for sc in daily_data:
            idx = np.argsort(np.array(daily_data[sc]['dates']))
            for k in daily_data[sc]:
                arr = np.array(daily_data[sc][k])[idx]
                daily_data[sc][k] = arr.astype(np.float64) if k != 'dates' else arr
        return daily_data
    
    def find_signals(self, daily_data: Dict, start_date: str, end_date: str) -> List[Dict]:
        all_signals = []
        for sc in sorted(daily_data.keys()):
            d = daily_data[sc]
            dates, close = d['dates'], d['close']
            high, low = d['high'], d['low']
            
            if len(close) < 50:
                continue
            
            mask = (dates >= start_date) & (dates <= end_date)
            if not np.any(mask):
                continue
            
            hist = calc_macd(close, self.macd_fast, self.macd_slow, self.macd_signal)
            rsi = calc_rsi(close, self.rsi_period)
            signals = detect_green_bar_contraction(hist)
            
            for i in range(len(signals) - 1):
                if not signals[i]:
                    continue
                
                if dates[i] < start_date or dates[i] > end_date:
                    continue
                
                if rsi[i] > self.rsi_max:
                    continue
                
                vs = calc_volatility_strength(close, high, low, i)
                if vs < self.vs_threshold:
                    continue
                
                buy_idx = i + 1
                if buy_idx >= len(close):
                    continue
                
                all_signals.append({
                    'stock_code': sc,
                    'signal_date': str(dates[i]),
                    'buy_date': str(dates[buy_idx]),
                    'buy_price': close[buy_idx],
                    'vs': vs,
                    'rsi': rsi[i],
                    'macd_hist': hist[i],
                })
        
        return all_signals
    
    def simulate_trades(self, signals: List[Dict], daily_data: Dict) -> Tuple[List[Dict], float]:
        trades = []
        for sig in signals:
            sc = sig['stock_code']
            d = daily_data[sc]
            dates, close = d['dates'], d['close']
            high, low = d['high'], d['low']
            
            buy_date = sig['buy_date']
            buy_idx = np.where(dates == buy_date)[0]
            if len(buy_idx) == 0:
                continue
            buy_idx = buy_idx[0]
            buy_price = close[buy_idx]
            peak_price = buy_price
            triggered = False
            sell_price = buy_price
            hold_days = 0
            
            for day in range(self.max_hold_days):
                chk = buy_idx + day
                if chk >= len(close):
                    sell_price = close[-1]
                    hold_days = day
                    break
                if high[chk] > peak_price:
                    peak_price = high[chk]
                if (high[chk] - buy_price) / buy_price >= self.trailing_trigger:
                    triggered = True
                if triggered and (peak_price - close[chk]) / peak_price >= self.trailing_drawdown:
                    sell_price = close[chk]
                    hold_days = day + 1
                    break
                sell_price = close[chk]
                hold_days = day + 1
            
            ret = (sell_price - buy_price) / buy_price
            sell_date = str(dates[min(buy_idx + hold_days, len(dates) - 1)])
            
            trades.append({
                **sig,
                'sell_date': sell_date,
                'sell_price': sell_price,
                'return': ret,
                'hold_days': hold_days,
            })
        
        trades_by_buy_date = defaultdict(list)
        for t in trades:
            trades_by_buy_date[t['buy_date']].append(t)
        
        for date in trades_by_buy_date:
            trades_by_buy_date[date].sort(key=lambda x: x['vs'], reverse=True)
        
        all_dates = set()
        for t in trades:
            all_dates.add(t['buy_date'])
            all_dates.add(t['sell_date'])
        all_dates = sorted(all_dates)
        
        initial_capital = 100000.0
        capital = initial_capital
        holdings = {}
        equity_curve = []
        
        for date in all_dates:
            for sc in list(holdings.keys()):
                h = holdings[sc]
                if h['sell_date'] == date:
                    capital += h['position_value'] * (1 + h['return'])
                    del holdings[sc]
            
            if date in trades_by_buy_date:
                for t in trades_by_buy_date[date]:
                    if t['stock_code'] in holdings:
                        continue
                    if len(holdings) < self.max_holdings:
                        position_value = initial_capital * self.position_size
                        capital -= position_value
                        holdings[t['stock_code']] = {
                            'position_value': position_value,
                            'return': t['return'],
                            'sell_date': t['sell_date'],
                        }
            
            equity_curve.append({
                'date': date,
                'equity': capital + sum(h['position_value'] * (1 + h['return']) for h in holdings.values())
            })
        
        for sc in holdings:
            capital += holdings[sc]['position_value'] * (1 + holdings[sc]['return'])
        
        total_return = (capital - initial_capital) / initial_capital * 100
        return equity_curve, total_return
    
    def run_backtest(self, start_date: str = "2015-01-01", end_date: str = "2025-12-31") -> Dict:
        print(f"加载股票数据...")
        daily_data = self.load_stock_data(start_date, end_date)
        print(f"股票数: {len(daily_data)}")
        
        print(f"寻找信号...")
        signals = self.find_signals(daily_data, start_date, end_date)
        print(f"信号数: {len(signals)}")
        
        print(f"模拟交易...")
        equity_curve, total_return = self.simulate_trades(signals, daily_data)
        
        return {
            'equity_curve': equity_curve,
            'total_return': total_return,
            'signal_count': len(signals),
            'config': self.config,
        }


def main():
    print("=" * 60)
    print("最优策略执行 - MACD绿柱收缩+波动率强度")
    print("=" * 60)
    
    strategy = OptimalStrategy()
    print(f"\n策略配置:")
    print(f"  名称: {strategy.config['strategy_name']}")
    print(f"  版本: {strategy.config['version']}")
    print(f"  VS阈值: {strategy.vs_threshold}")
    print(f"  RSI上限: {strategy.rsi_max}")
    print(f"  最大持仓: {strategy.max_holdings}")
    print(f"  仓位比例: {strategy.position_size*100}%")
    
    result = strategy.run_backtest()
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"  信号数: {result['signal_count']}")
    print(f"  总收益: {result['total_return']:.1f}%")
    
    perf = strategy.config['performance']
    print(f"\n配置文件记录的收益: {perf['total_return_pct']:.1f}%")
    print(f"超额收益: {perf['excess_return_pct']:.1f}%")


if __name__ == "__main__":
    main()
