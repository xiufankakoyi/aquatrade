"""
条件3极致优化版本 - 使用 Numba + Polars + 预计算

优化策略：
1. 预计算所有日期的板块内涨幅排名（一次性计算，多次使用）
2. 使用 Numba 加速 MACD 和信号检测
3. 使用 Polars 向量化操作
4. 数据结构优化（numpy 数组替代 list）
5. 使用封装的 LanceDBDataReader 接口（支持指定列读取）
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import polars as pl
import lancedb
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from numba import jit, prange
from time import time

from config.logger import get_logger
from data_svc.storage.unified_reader import get_lancedb_reader

logger = get_logger(__name__)


@dataclass
class OptimizedCache:
    """优化后的缓存数据结构"""
    stock_codes: np.ndarray
    trading_dates: np.ndarray
    date_to_idx: Dict[str, int]
    
    stock_info_arr: np.ndarray
    industry_arr: np.ndarray
    
    close_matrix: np.ndarray
    volume_matrix: np.ndarray
    dates_matrix: np.ndarray
    
    sector_pct_chg: Dict[str, np.ndarray]
    sector_limit_up: Dict[str, np.ndarray]
    sector_index: Dict[str, np.ndarray]
    sector_ma20: Dict[str, np.ndarray]
    
    stock_rank_matrix: np.ndarray
    
    industry_to_idx: Dict[str, int]
    stock_to_idx: Dict[str, int]


_cache_optimized = None


@jit(nopython=True, cache=True, fastmath=True)
def calculate_macd_fast(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """极速 MACD 计算"""
    n = len(close)
    histogram = np.empty(n, dtype=np.float64)
    
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    alpha_signal = 2.0 / (signal + 1)
    
    ema_fast = close[0]
    ema_slow = close[0]
    dea = 0.0
    
    for i in range(n):
        ema_fast = alpha_fast * close[i] + (1 - alpha_fast) * ema_fast
        ema_slow = alpha_slow * close[i] + (1 - alpha_slow) * ema_slow
        dif = ema_fast - ema_slow
        dea = alpha_signal * dif + (1 - alpha_signal) * dea
        histogram[i] = (dif - dea) * 2
    
    return histogram


@jit(nopython=True, cache=True, fastmath=True)
def calculate_volume_ma_fast(volume: np.ndarray, period: int = 5):
    """极速成交量均线"""
    n = len(volume)
    result = np.empty(n, dtype=np.float64)
    
    cumsum = 0.0
    for i in range(n):
        cumsum += volume[i]
        if i >= period:
            cumsum -= volume[i - period]
        result[i] = cumsum / min(i + 1, period)
    
    return result


@jit(nopython=True, cache=True, fastmath=True)
def detect_signals_fast(
    histogram: np.ndarray,
    volume: np.ndarray,
    volume_ma5: np.ndarray,
    min_volume_ratio: float,
):
    """极速信号检测 - 返回买入信号索引"""
    n = len(histogram)
    signals = np.empty(n, dtype=np.int32)
    count = 0
    
    for i in range(4, n):
        bars_0 = histogram[i-3]
        bars_1 = histogram[i-2]
        bars_2 = histogram[i-1]
        bars_3 = histogram[i]
        
        if bars_0 < 0 and bars_1 < 0 and bars_2 < 0 and bars_3 < 0:
            if bars_0 < bars_1 and bars_1 < bars_2 and bars_2 < bars_3:
                diff1 = bars_1 - bars_0
                diff2 = bars_2 - bars_1
                diff3 = bars_3 - bars_2
                
                if diff1 < diff2 and diff2 < diff3:
                    vol_ratio = volume[i] / volume_ma5[i] if volume_ma5[i] > 0 else 0
                    if vol_ratio >= min_volume_ratio:
                        signals[count] = i
                        count += 1
    
    return signals[:count]


@jit(nopython=True, cache=True, fastmath=True)
def check_sell_fast(histogram: np.ndarray, buy_idx: int, max_days: int):
    """检查卖出条件"""
    n = len(histogram)
    for j in range(buy_idx + 1, min(buy_idx + max_days + 1, n)):
        if histogram[j] > 0 and j > 0 and histogram[j] < histogram[j - 1]:
            return j, j - buy_idx
    return -1, -1


def preload_optimized(
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
) -> OptimizedCache:
    """预加载数据并构建优化数据结构"""
    print("\n" + "="*60)
    print("预加载数据 (优化版)")
    print("="*60)
    
    t0 = time()
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print("\n[1/6] 加载股票信息...")
    table = db.open_table("stock_info")
    stock_info_df = pl.from_arrow(table.to_arrow())
    
    stock_codes = stock_info_df['stock_code'].to_numpy()
    industries = stock_info_df['industry'].fill_null('未知').to_numpy()
    
    stock_to_idx = {code: i for i, code in enumerate(stock_codes)}
    unique_industries = np.unique(industries)
    industry_to_idx = {ind: i for i, ind in enumerate(unique_industries)}
    industry_arr = np.array([industry_to_idx.get(ind, -1) for ind in industries], dtype=np.int32)
    
    print(f"  股票数: {len(stock_codes)}, 行业数: {len(unique_industries)}")
    
    print("\n[2/6] 加载日线数据...")
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_df = daily_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    trading_dates = daily_df.select('trade_date').unique().sort('trade_date')['trade_date'].to_numpy()
    trading_dates_str = np.array([str(d) for d in trading_dates])
    date_to_idx = {str(d): i for i, d in enumerate(trading_dates)}
    T = len(trading_dates)
    N = len(stock_codes)
    
    print(f"  交易日: {T}, 股票: {N}")
    
    print("\n[3/6] 构建价格矩阵（向量化）...")
    close_matrix = np.full((T, N), np.nan, dtype=np.float64)
    volume_matrix = np.full((T, N), np.nan, dtype=np.float64)
    
    date_df = pl.DataFrame({'trade_date': trading_dates}).with_row_index('date_idx')
    stock_df = pl.DataFrame({'stock_code': stock_codes}).with_row_index('stock_idx')
    
    daily_with_idx = daily_df.join(date_df, on='trade_date').join(stock_df, on='stock_code')
    
    date_indices = daily_with_idx['date_idx'].to_numpy()
    stock_indices = daily_with_idx['stock_idx'].to_numpy()
    close_values = daily_with_idx['close'].to_numpy()
    volume_values = daily_with_idx['volume'].to_numpy()
    
    close_matrix[date_indices, stock_indices] = close_values
    volume_matrix[date_indices, stock_indices] = volume_values
    
    for s in range(N):
        mask = ~np.isnan(close_matrix[:, s])
        if np.any(mask):
            close_matrix[:, s] = np.interp(
                np.arange(T), 
                np.where(mask)[0], 
                close_matrix[mask, s]
            )
            volume_matrix[:, s] = np.interp(
                np.arange(T),
                np.where(mask)[0],
                volume_matrix[mask, s]
            )
    
    print(f"  矩阵形状: {close_matrix.shape}")
    
    print("\n[4/6] 加载板块数据...")
    table = db.open_table("sector_daily")
    sector_df = pl.from_arrow(table.to_arrow())
    sector_df = sector_df.filter(
        (pl.col('trade_date').cast(pl.Utf8) >= start_date) &
        (pl.col('trade_date').cast(pl.Utf8) <= end_date)
    )
    
    sector_pct_chg = {}
    sector_limit_up = {}
    sector_index = {}
    sector_ma20 = {}
    
    for ind_name in unique_industries:
        ind_data = sector_df.filter(pl.col('sector_name') == ind_name)
        if len(ind_data) == 0:
            continue
        
        ind_data = ind_data.sort('trade_date')
        dates_ind = ind_data['trade_date'].to_numpy()
        
        pct_arr = np.full(T, 0.0, dtype=np.float64)
        limit_arr = np.full(T, 0, dtype=np.int32)
        idx_arr = np.full(T, 1000.0, dtype=np.float64)
        ma20_arr = np.full(T, np.nan, dtype=np.float64)
        
        for row in ind_data.iter_rows(named=True):
            t = date_to_idx.get(str(row['trade_date']), -1)
            if t >= 0:
                pct_arr[t] = row.get('weighted_pct_change') or 0
                limit_arr[t] = row.get('limit_up_count') or 0
                idx_arr[t] = row.get('sector_index') or 1000
        
        valid = idx_arr != 1000
        if np.sum(valid) >= 20:
            ma20 = np.convolve(idx_arr[valid], np.ones(20)/20, mode='valid')
            ma20_arr[19:19+len(ma20)] = ma20
        
        sector_pct_chg[ind_name] = pct_arr
        sector_limit_up[ind_name] = limit_arr
        sector_index[ind_name] = idx_arr
        sector_ma20[ind_name] = ma20_arr
    
    print(f"  板块数: {len(sector_pct_chg)}")
    
    print("\n[5/6] 预计算板块内涨幅排名（向量化）...")
    pct_chg_matrix = np.full((T, N), np.nan, dtype=np.float64)
    pct_chg_matrix[1:, :] = (close_matrix[1:, :] - close_matrix[:-1, :]) / close_matrix[:-1, :] * 100
    
    stock_rank_matrix = np.full((T, N), 50.0, dtype=np.float64)
    
    for ind_idx in range(len(unique_industries)):
        ind_mask = industry_arr == ind_idx
        ind_stock_indices = np.where(ind_mask)[0]
        
        if len(ind_stock_indices) == 0:
            continue
        
        ind_pct = pct_chg_matrix[:, ind_stock_indices]
        
        for t in range(1, T):
            valid_mask = ~np.isnan(ind_pct[t, :])
            if np.sum(valid_mask) == 0:
                continue
            
            valid_pct = ind_pct[t, valid_mask]
            valid_indices = ind_stock_indices[valid_mask]
            
            sorted_order = np.argsort(valid_pct)[::-1]
            n_valid = len(valid_pct)
            
            for rank, idx in enumerate(sorted_order):
                stock_rank_matrix[t, valid_indices[idx]] = (n_valid - rank) / n_valid * 100
    
    print(f"  排名矩阵: {stock_rank_matrix.shape}")
    
    print("\n[6/6] 构建缓存对象...")
    
    cache = OptimizedCache(
        stock_codes=stock_codes,
        trading_dates=trading_dates_str,
        date_to_idx=date_to_idx,
        stock_info_arr=np.zeros(N, dtype=np.int32),
        industry_arr=industry_arr,
        close_matrix=close_matrix,
        volume_matrix=volume_matrix,
        dates_matrix=np.arange(T * N).reshape(T, N),
        sector_pct_chg=sector_pct_chg,
        sector_limit_up=sector_limit_up,
        sector_index=sector_index,
        sector_ma20=sector_ma20,
        stock_rank_matrix=stock_rank_matrix,
        industry_to_idx=industry_to_idx,
        stock_to_idx=stock_to_idx,
    )
    
    t1 = time()
    print(f"\n✅ 预加载完成! 耗时: {t1-t0:.2f}秒")
    print("="*60)
    
    return cache


def get_optimized_cache() -> OptimizedCache:
    """获取优化缓存（单例）"""
    global _cache_optimized
    if _cache_optimized is None:
        _cache_optimized = preload_optimized()
    return _cache_optimized


def run_backtest_fast(
    min_volume_ratio: float = 1.5,
    rank_top_pct: float = 20.0,
    max_hold_days: int = 60,
) -> Dict:
    """极速回测"""
    cache = get_optimized_cache()
    
    t0 = time()
    
    close = cache.close_matrix
    volume = cache.volume_matrix
    rank = cache.stock_rank_matrix
    industry_arr = cache.industry_arr
    
    T, N = close.shape
    
    rank_threshold = 100 - rank_top_pct
    
    results = []
    
    for s in range(N):
        close_s = close[:, s]
        volume_s = volume[:, s]
        
        if np.any(np.isnan(close_s)):
            continue
        
        histogram = calculate_macd_fast(close_s)
        volume_ma5 = calculate_volume_ma_fast(volume_s)
        
        buy_signals = detect_signals_fast(histogram, volume_s, volume_ma5, min_volume_ratio)
        
        for i in range(len(buy_signals)):
            sig_idx = buy_signals[i]
            buy_idx = sig_idx + 1
            
            if buy_idx >= T - 3:
                continue
            
            if rank[sig_idx, s] < rank_threshold:
                continue
            
            buy_price = close[buy_idx, s]
            
            sell_idx, hold_days = check_sell_fast(histogram, buy_idx, max_hold_days)
            
            if sell_idx > 0:
                sell_price = close[sell_idx, s]
                ret = (sell_price - buy_price) / buy_price * 100
                
                results.append({
                    'stock_idx': s,
                    'buy_idx': buy_idx,
                    'sell_idx': sell_idx,
                    'hold_days': hold_days,
                    'return': ret,
                    'rank': rank[sig_idx, s],
                })
            else:
                sell_idx = min(buy_idx + max_hold_days, T - 1)
                sell_price = close[sell_idx, s]
                ret = (sell_price - buy_price) / buy_price * 100
                
                results.append({
                    'stock_idx': s,
                    'buy_idx': buy_idx,
                    'sell_idx': sell_idx,
                    'hold_days': max_hold_days,
                    'return': ret,
                    'rank': rank[sig_idx, s],
                })
    
    t1 = time()
    
    if not results:
        return {'error': 'no results', 'time': t1-t0}
    
    df = pl.DataFrame(results)
    
    returns = df['return'].to_numpy()
    hold_days = df['hold_days'].to_numpy()
    
    n = len(returns)
    win_count = np.sum(returns > 0)
    lose_count = np.sum(returns < 0)
    win_rate = win_count / n * 100
    
    return {
        'total_trades': n,
        'win_count': int(win_count),
        'lose_count': int(lose_count),
        'win_rate': win_rate,
        'avg_return': np.mean(returns),
        'median_return': np.median(returns),
        'avg_hold_days': np.mean(hold_days),
        'profit_factor': abs(np.sum(returns[returns > 0]) / np.sum(returns[returns < 0])) if np.sum(returns[returns < 0]) != 0 else float('inf'),
        'time': t1 - t0,
    }


def grid_search(
    volume_ratios: List[float] = [1.0, 1.2, 1.5, 2.0],
    rank_top_pcts: List[float] = [10, 20, 30, 40, 50],
    max_hold_days_list: List[int] = [10, 20, 30, 60],
):
    """网格搜索最优参数"""
    print("\n" + "="*70)
    print("网格搜索最优参数")
    print("="*70)
    
    cache = get_optimized_cache()
    
    print(f"\n参数空间:")
    print(f"  min_volume_ratio: {volume_ratios}")
    print(f"  rank_top_pct: {rank_top_pcts}")
    print(f"  max_hold_days: {max_hold_days_list}")
    print(f"  总组合数: {len(volume_ratios) * len(rank_top_pcts) * len(max_hold_days_list)}")
    
    results = []
    
    print(f"\n{'volume_ratio':>12} {'rank_top%':>10} {'max_hold':>10} {'trades':>8} {'win_rate':>8} {'avg_ret':>8} {'pf':>6} {'time':>6}")
    print("-" * 70)
    
    for vol in volume_ratios:
        for rank_pct in rank_top_pcts:
            for max_hold in max_hold_days_list:
                result = run_backtest_fast(
                    min_volume_ratio=vol,
                    rank_top_pct=rank_pct,
                    max_hold_days=max_hold,
                )
                
                if 'error' not in result:
                    results.append({
                        'volume_ratio': vol,
                        'rank_top_pct': rank_pct,
                        'max_hold_days': max_hold,
                        **result
                    })
                    
                    print(f"{vol:>12.1f} {rank_pct:>10.0f}% {max_hold:>10d} "
                          f"{result['total_trades']:>8d} {result['win_rate']:>7.1f}% "
                          f"{result['avg_return']:>7.2f}% {result['profit_factor']:>6.2f} "
                          f"{result['time']:>5.2f}s")
    
    if results:
        df = pl.DataFrame(results)
        df = df.sort('avg_return', descending=True)
        
        print(f"\n{'='*70}")
        print("Top 5 参数组合 (按平均收益排序)")
        print("="*70)
        
        for row in df.head(5).iter_rows(named=True):
            print(f"\n  volume_ratio={row['volume_ratio']}, rank_top_pct={row['rank_top_pct']}%, "
                  f"max_hold_days={row['max_hold_days']}")
            print(f"  交易数: {row['total_trades']}, 胜率: {row['win_rate']:.1f}%, "
                  f"平均收益: {row['avg_return']:.2f}%, 盈利因子: {row['profit_factor']:.2f}")
    
    return results


if __name__ == "__main__":
    print("\n[测试极速回测]")
    result = run_backtest_fast(min_volume_ratio=1.5, rank_top_pct=20, max_hold_days=60)
    print(f"\n结果: {result}")
    
    print("\n" + "="*70)
    print("[网格搜索]")
    grid_search()
