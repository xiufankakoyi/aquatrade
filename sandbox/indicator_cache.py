"""
指标缓存层
=========
跨策略指标缓存系统，避免重复计算相同指标。

核心特性:
1. 跨策略共享: 不同策略使用相同指标时共享缓存
2. 预计算: 回测开始前批量计算整个时间段的指标
3. Numba 加速: 使用 Numba JIT 编译的向量化计算
4. 内存高效: 使用 Polars LazyFrame 惰性计算

使用方法:
    from sandbox.indicator_cache import IndicatorCache
    
    cache = IndicatorCache()
    
    # 预计算指标
    cache.warmup(
        codes=['000001.SZ', '000002.SZ'],
        dates=['2024-01-01', '2024-01-02'],
        indicators=[
            {'type': 'ma', 'window': 20},
            {'type': 'rsi', 'window': 14},
        ]
    )
    
    # 获取指标
    ma20 = cache.get('000001.SZ', '2024-01-15', 'ma_20')
"""

import hashlib
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from functools import lru_cache
import time

import pandas as pd
import polars as pl
import numpy as np

# Numba 加速
try:
    from numba import jit, njit
    from core.calc.vectorized_ops import (
        calc_ma_vectorized,
        calc_cross_over,
        calc_cross_under
    )
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    njit = lambda *args, **kwargs: (lambda f: f)


@dataclass
class IndicatorKey:
    """指标缓存键"""
    code: str
    date: str
    indicator_type: str
    params_hash: str
    
    def __hash__(self):
        return hash((self.code, self.date, self.indicator_type, self.params_hash))
    
    def __eq__(self, other):
        return (self.code == other.code and 
                self.date == other.date and 
                self.indicator_type == other.indicator_type and 
                self.params_hash == other.params_hash)


class IndicatorCache:
    """
    指标缓存层
    
    提供跨策略的指标缓存，支持预计算和惰性计算。
    """
    
    def __init__(self, max_size: int = 10000):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
        """
        self._cache: Dict[IndicatorKey, Any] = {}
        self._max_size = max_size
        self._access_count: Dict[IndicatorKey, int] = {}
        
        # 性能统计
        self._stats = {
            'hits': 0,
            'misses': 0,
            'computations': 0,
        }
    
    def _make_key(
        self,
        code: str,
        date: str,
        indicator_type: str,
        params: Dict[str, Any]
    ) -> IndicatorKey:
        """创建缓存键"""
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        return IndicatorKey(code, date, indicator_type, params_hash)
    
    def get(
        self,
        code: str,
        date: str,
        indicator_type: str,
        params: Optional[Dict[str, Any]] = None,
        compute_func: Optional[Callable] = None
    ) -> Any:
        """
        获取指标值
        
        Args:
            code: 股票代码
            date: 日期
            indicator_type: 指标类型
            params: 指标参数
            compute_func: 计算函数（缓存未命中时使用）
        
        Returns:
            指标值
        """
        key = self._make_key(code, date, indicator_type, params or {})
        
        if key in self._cache:
            self._stats['hits'] += 1
            self._access_count[key] = self._access_count.get(key, 0) + 1
            return self._cache[key]
        
        self._stats['misses'] += 1
        
        # 如果有计算函数，计算并缓存
        if compute_func:
            value = compute_func()
            self.set(code, date, indicator_type, params, value)
            return value
        
        return None
    
    def set(
        self,
        code: str,
        date: str,
        indicator_type: str,
        params: Optional[Dict[str, Any]],
        value: Any
    ) -> None:
        """
        设置缓存值
        
        Args:
            code: 股票代码
            date: 日期
            indicator_type: 指标类型
            params: 指标参数
            value: 指标值
        """
        key = self._make_key(code, date, indicator_type, params or {})
        
        # LRU 淘汰
        if len(self._cache) >= self._max_size:
            self._evict_lru()
        
        self._cache[key] = value
        self._access_count[key] = 1
    
    def _evict_lru(self):
        """淘汰最少使用的缓存项"""
        if not self._cache:
            return
        
        # 找到访问次数最少的键
        min_key = min(self._access_count.keys(), key=lambda k: self._access_count[k])
        del self._cache[min_key]
        del self._access_count[min_key]
    
    def warmup(
        self,
        price_matrix: np.ndarray,
        codes: List[str],
        dates: List[str],
        indicators_config: List[Dict[str, Any]]
    ) -> None:
        """
        预计算指标
        
        批量计算整个回测期间的指标，避免运行时重复计算。
        
        Args:
            price_matrix: 价格矩阵 (T, N, 4) [open, high, low, close]
            codes: 股票代码列表
            dates: 日期列表
            indicators_config: 指标配置列表
        """
        print(f"[IndicatorCache] 开始预计算 {len(indicators_config)} 个指标...")
        start_time = time.time()
        
        T, N, _ = price_matrix.shape
        close_prices = price_matrix[:, :, 3]  # close 在第 3 列
        
        for config in indicators_config:
            indicator_type = config.get('type')
            window = config.get('window', 14)
            
            if indicator_type == 'ma':
                # 计算移动平均线
                ma_values = self._calc_ma_batch(close_prices, window)
                
                # 缓存结果
                for t, date in enumerate(dates):
                    for n, code in enumerate(codes):
                        value = ma_values[t, n]
                        if not np.isnan(value):
                            self.set(code, date, f'ma_{window}', {'window': window}, value)
            
            elif indicator_type == 'rsi':
                # 计算 RSI
                rsi_values = self._calc_rsi_batch(close_prices, window)
                
                for t, date in enumerate(dates):
                    for n, code in enumerate(codes):
                        value = rsi_values[t, n]
                        if not np.isnan(value):
                            self.set(code, date, f'rsi_{window}', {'window': window}, value)
            
            elif indicator_type == 'macd':
                # 计算 MACD
                fast = config.get('fast', 12)
                slow = config.get('slow', 26)
                signal = config.get('signal', 9)
                
                macd_values = self._calc_macd_batch(close_prices, fast, slow, signal)
                
                for t, date in enumerate(dates):
                    for n, code in enumerate(codes):
                        dif, dea, hist = macd_values[t, n]
                        if not np.isnan(dif):
                            self.set(code, date, f'macd_dif', {'fast': fast, 'slow': slow}, dif)
                            self.set(code, date, f'macd_dea', {'signal': signal}, dea)
                            self.set(code, date, f'macd_hist', {}, hist)
            
            self._stats['computations'] += T * N
        
        duration = time.time() - start_time
        print(f"[IndicatorCache] 预计算完成: {len(self._cache)} 个缓存项, 耗时 {duration:.2f}s")
    
    def _calc_ma_batch(self, prices: np.ndarray, window: int) -> np.ndarray:
        """
        批量计算移动平均线
        
        Args:
            prices: (T, N) 价格矩阵
            window: 窗口大小
        
        Returns:
            (T, N) MA 值矩阵
        """
        T, N = prices.shape
        ma = np.full((T, N), np.nan)
        
        if NUMBA_AVAILABLE:
            ma = calc_ma_vectorized(prices, window)
        else:
            # 纯 NumPy 实现
            for n in range(N):
                valid_prices = prices[:, n]
                # 使用卷积计算移动平均
                kernel = np.ones(window) / window
                ma[:, n] = np.convolve(valid_prices, kernel, mode='same')
        
        return ma
    
    def _calc_rsi_batch(self, prices: np.ndarray, window: int = 14) -> np.ndarray:
        """
        批量计算 RSI
        
        Args:
            prices: (T, N) 价格矩阵
            window: RSI 周期
        
        Returns:
            (T, N) RSI 值矩阵
        """
        T, N = prices.shape
        rsi = np.full((T, N), np.nan)
        
        # 计算价格变化
        deltas = np.diff(prices, axis=0, prepend=prices[:1])
        
        # 分离上涨和下跌
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # 计算平均上涨和下跌
        avg_gains = np.full((T, N), np.nan)
        avg_losses = np.full((T, N), np.nan)
        
        for n in range(N):
            # 使用指数移动平均
            valid_gains = gains[:, n]
            valid_losses = losses[:, n]
            
            # 简单移动平均作为初始值
            for t in range(window, T):
                avg_gains[t, n] = np.mean(valid_gains[t-window:t])
                avg_losses[t, n] = np.mean(valid_losses[t-window:t])
        
        # 计算 RSI
        rs = avg_gains / (avg_losses + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calc_macd_batch(
        self,
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> np.ndarray:
        """
        批量计算 MACD
        
        Returns:
            (T, N, 3) [DIF, DEA, HIST]
        """
        T, N = prices.shape
        macd = np.full((T, N, 3), np.nan)
        
        # 计算 EMA
        ema_fast = self._calc_ema_batch(prices, fast)
        ema_slow = self._calc_ema_batch(prices, slow)
        
        # DIF = EMA(fast) - EMA(slow)
        dif = ema_fast - ema_slow
        
        # DEA = EMA(DIF, signal)
        dea = self._calc_ema_batch(dif, signal)
        
        # HIST = DIF - DEA
        hist = dif - dea
        
        macd[:, :, 0] = dif
        macd[:, :, 1] = dea
        macd[:, :, 2] = hist
        
        return macd
    
    def _calc_ema_batch(self, prices: np.ndarray, window: int) -> np.ndarray:
        """批量计算 EMA"""
        T, N = prices.shape
        ema = np.full((T, N), np.nan)
        
        alpha = 2 / (window + 1)
        
        for n in range(N):
            valid_prices = prices[:, n]
            
            # 初始值使用 SMA
            if len(valid_prices) >= window:
                ema[window-1, n] = np.mean(valid_prices[:window])
                
                for t in range(window, T):
                    ema[t, n] = alpha * valid_prices[t] + (1 - alpha) * ema[t-1, n]
        
        return ema
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            'computations': self._stats['computations'],
        }
    
    def print_stats(self):
        """打印缓存统计"""
        stats = self.get_cache_stats()
        print("=" * 60)
        print("指标缓存统计")
        print("=" * 60)
        print(f"缓存大小: {stats['cache_size']} / {stats['max_size']}")
        print(f"缓存命中: {stats['hits']}")
        print(f"缓存未命中: {stats['misses']}")
        print(f"命中率: {stats['hit_rate']*100:.1f}%")
        print(f"预计算次数: {stats['computations']}")
        print("=" * 60)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_count.clear()
        self._stats = {'hits': 0, 'misses': 0, 'computations': 0}


# ==================== 便捷函数 ====================

def create_indicator_cache(max_size: int = 10000) -> IndicatorCache:
    """创建默认指标缓存"""
    return IndicatorCache(max_size)


def warmup_indicators(
    cache: IndicatorCache,
    price_matrix: np.ndarray,
    codes: List[str],
    dates: List[str],
    indicators: List[Dict[str, Any]]
) -> None:
    """便捷的预计算函数"""
    cache.warmup(price_matrix, codes, dates, indicators)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("指标缓存层测试")
    print("=" * 60)
    
    # 创建缓存
    cache = IndicatorCache(max_size=1000)
    
    # 测试 1: 基本缓存操作
    print("\n[测试 1] 基本缓存操作")
    cache.set('000001.SZ', '2024-01-15', 'ma_20', {'window': 20}, 10.5)
    
    value = cache.get('000001.SZ', '2024-01-15', 'ma_20', {'window': 20})
    print(f"  获取缓存值: {value}")
    
    # 测试 2: 缓存命中
    print("\n[测试 2] 缓存命中")
    value2 = cache.get('000001.SZ', '2024-01-15', 'ma_20', {'window': 20})
    print(f"  再次获取: {value2}")
    
    stats = cache.get_cache_stats()
    print(f"  命中率: {stats['hit_rate']*100:.1f}%")
    
    # 测试 3: 批量计算 MA
    print("\n[测试 3] 批量计算 MA")
    
    # 创建测试价格矩阵 (T=10, N=3)
    np.random.seed(42)
    price_matrix = np.random.randn(10, 3, 4).cumsum(axis=0) + 10
    price_matrix = np.abs(price_matrix)  # 确保正数
    
    codes = ['000001.SZ', '000002.SZ', '000003.SZ']
    dates = [f'2024-01-{i+1:02d}' for i in range(10)]
    
    indicators_config = [
        {'type': 'ma', 'window': 5},
        {'type': 'ma', 'window': 10},
    ]
    
    cache.warmup(price_matrix, codes, dates, indicators_config)
    
    print(f"  缓存项数: {len(cache._cache)}")
    
    # 测试 4: 获取预计算的指标
    print("\n[测试 4] 获取预计算指标")
    ma5 = cache.get('000001.SZ', '2024-01-10', 'ma_5', {'window': 5})
    ma10 = cache.get('000001.SZ', '2024-01-10', 'ma_10', {'window': 10})
    
    print(f"  MA5: {ma5}")
    print(f"  MA10: {ma10}")
    
    # 打印统计
    print("\n")
    cache.print_stats()
    
    print("\n测试完成!")
