"""
数据预加载模块 - 将数据加载到内存中持久化

避免每次测试都重新加载数据
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import lancedb
from numba import jit

from config.logger import get_logger

logger = get_logger(__name__)

_cache = None
_cache_params = None


@dataclass
class PreloadedData:
    """预加载数据结构"""
    stock_info: Dict[str, dict] = field(default_factory=dict)
    daily_data: Dict[str, dict] = field(default_factory=dict)
    sector_data: Dict[str, dict] = field(default_factory=dict)
    trading_dates: List[str] = field(default_factory=list)
    stock_codes: List[str] = field(default_factory=list)


def get_cache(start_date: str = "2013-01-01", end_date: str = "2025-12-31") -> PreloadedData:
    """获取缓存数据（单例模式）"""
    global _cache, _cache_params
    
    if _cache is None or _cache_params != (start_date, end_date):
        _cache = preload_data(start_date, end_date)
        _cache_params = (start_date, end_date)
    return _cache


def preload_data(
    start_date: str = "2013-01-01",
    end_date: str = "2025-12-31",
) -> PreloadedData:
    """预加载所有数据到内存"""
    print("\n" + "="*60)
    print("预加载数据到内存")
    print(f"时间范围: {start_date} - {end_date}")
    print("="*60)
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    data = PreloadedData()
    
    print("\n[1/4] 加载股票信息...")
    table = db.open_table("stock_info")
    stock_info_df = pl.from_arrow(table.to_arrow())
    for row in stock_info_df.iter_rows(named=True):
        data.stock_info[row['stock_code']] = {
            'name': row.get('stock_name', ''),
            'industry': row.get('industry'),
        }
    print(f"  股票信息: {len(data.stock_info)} 只")
    
    print("\n[2/4] 加载日线数据...")
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_df = daily_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    for row in daily_df.iter_rows(named=True):
        stock_code = row['stock_code']
        if stock_code not in data.daily_data:
            data.daily_data[stock_code] = {
                'dates': [],
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
                'amount': [],
            }
        data.daily_data[stock_code]['dates'].append(str(row['trade_date']))
        data.daily_data[stock_code]['open'].append(row.get('open', row.get('close')))
        data.daily_data[stock_code]['high'].append(row.get('high', row.get('close')))
        data.daily_data[stock_code]['low'].append(row.get('low', row.get('close')))
        data.daily_data[stock_code]['close'].append(row['close'])
        data.daily_data[stock_code]['volume'].append(row['volume'])
        data.daily_data[stock_code]['amount'].append(row.get('amount', 0))
    
    for stock_code in data.daily_data:
        dates_arr = np.array(data.daily_data[stock_code]['dates'])
        sorted_idx = np.argsort(dates_arr)
        
        for key in ['dates', 'open', 'high', 'low', 'close', 'volume', 'amount']:
            arr = np.array(data.daily_data[stock_code][key])
            data.daily_data[stock_code][key] = arr[sorted_idx]
    
    data.stock_codes = list(data.daily_data.keys())
    print(f"  日线数据: {len(data.stock_codes)} 只股票")
    
    print("\n[3/4] 加载板块数据...")
    table = db.open_table("sector_daily")
    sector_df = pl.from_arrow(table.to_arrow())
    sector_df = sector_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    for row in sector_df.iter_rows(named=True):
        date_str = str(row['trade_date'])
        sector_name = row['sector_name']
        if date_str not in data.sector_data:
            data.sector_data[date_str] = {}
        
        up_count = row.get('up_count') or 0
        stock_count = row.get('stock_count') or 1
        limit_up_count = row.get('limit_up_count') or 0
        
        data.sector_data[date_str][sector_name] = {
            'pct_chg': row.get('weighted_pct_change') or 0,
            'up_ratio': up_count / stock_count if stock_count > 0 else 0,
            'up_count': up_count,
            'stock_count': stock_count,
            'limit_up_count': limit_up_count,
            'total_amount': row.get('total_amount') or 0,
            'sector_index': row.get('sector_index') or 1000,
        }
    
    print(f"  板块数据: {len(data.sector_data)} 天")
    
    print("\n[4/4] 计算板块均线...")
    all_dates = sorted(data.sector_data.keys())
    all_sectors = set()
    for date_str in data.sector_data:
        all_sectors.update(data.sector_data[date_str].keys())
    
    for sector in all_sectors:
        indices = []
        dates_with_sector = []
        for date_str in all_dates:
            if sector in data.sector_data[date_str]:
                indices.append(data.sector_data[date_str][sector]['sector_index'])
                dates_with_sector.append(date_str)
        
        if len(indices) >= 20:
            indices = np.array(indices)
            ma20 = np.convolve(indices, np.ones(20)/20, mode='valid')
            
            for i, date_str in enumerate(dates_with_sector[19:]):
                if sector in data.sector_data[date_str]:
                    data.sector_data[date_str][sector]['ma20'] = ma20[i]
    
    data.trading_dates = all_dates
    print(f"  交易日: {len(data.trading_dates)} 天")
    
    print("\n" + "="*60)
    print("数据预加载完成!")
    print("="*60)
    
    return data


@jit(nopython=True, cache=True)
def calculate_macd_numba(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    n = len(close)
    dif = np.empty(n, dtype=np.float64)
    dea = np.empty(n, dtype=np.float64)
    histogram = np.empty(n, dtype=np.float64)
    
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    alpha_signal = 2.0 / (signal + 1)
    
    ema_fast = close[0]
    ema_slow = close[0]
    
    for i in range(n):
        ema_fast = alpha_fast * close[i] + (1 - alpha_fast) * ema_fast
        ema_slow = alpha_slow * close[i] + (1 - alpha_slow) * ema_slow
        dif[i] = ema_fast - ema_slow
    
    dea[0] = dif[0]
    for i in range(1, n):
        dea[i] = alpha_signal * dif[i] + (1 - alpha_signal) * dea[i - 1]
    
    for i in range(n):
        histogram[i] = (dif[i] - dea[i]) * 2
    
    return dif, dea, histogram


@jit(nopython=True, cache=True)
def calculate_volume_ma_numba(volume: np.ndarray, period: int = 5):
    n = len(volume)
    result = np.empty(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - period + 1)
        result[i] = np.mean(volume[start:i+1])
    return result


if __name__ == "__main__":
    data = get_cache()
    print(f"\n缓存已就绪，包含 {len(data.stock_codes)} 只股票")
