"""
优化后的数据服务 - 高性能数据查询

主要优化：
1. 多级缓存 (内存 + 磁盘)
2. 连接池复用
3. 批量查询
4. 异步加载
5. 数据预取
"""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache

import numpy as np
import polars as pl

from config.logger import get_logger
from server.performance_optimizer import (
    cached, monitor_performance, ConnectionPool,
    DataCompressor, _global_cache
)

logger = get_logger(__name__)


class OptimizedDataService:
    """
    优化后的数据服务
    
    单例模式，全局复用连接和缓存
    """
    
    _instance: Optional['OptimizedDataService'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.logger = get_logger(__name__)
        
        # 线程池用于并行查询
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="data_query")
        
        # 连接池
        self._connection_pool = ConnectionPool(max_connections=20)
        
        # 热点数据缓存
        self._hot_data_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # 预加载状态
        self._preloaded = False
    
    # ========================================================================
    # 1. 股票数据查询 (带缓存)
    # ========================================================================
    
    @cached(ttl=300, key_prefix="stock_daily")
    @monitor_performance
    def get_stock_daily(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: Optional[List[str]] = None
    ) -> Optional[pl.DataFrame]:
        """
        获取股票日线数据 (带缓存)
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 需要的字段
            
        Returns:
            Polars DataFrame 或 None
        """
        try:
            from data_svc.database.polars_data_loader_v4 import PolarsDataLoaderV4
            
            loader = PolarsDataLoaderV4()
            
            # 使用 scan_parquet 进行高效查询
            daily_path = loader.parquet_dir / "stock_daily.parquet"
            
            if not daily_path.exists():
                self.logger.warning(f"[DataService] 数据文件不存在: {daily_path}")
                return None
            
            # 构建查询
            lf = pl.scan_parquet(daily_path)
            lf = lf.filter(
                (pl.col('stock_code') == symbol) &
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date) &
                (pl.col('volume') > 0)
            )
            
            if fields:
                available_fields = ['stock_code', 'trade_date'] + fields
                lf = lf.select(available_fields)
            
            df = lf.collect()
            
            if df.is_empty():
                return None
            
            return df
            
        except Exception as e:
            self.logger.error(f"[DataService] 获取股票数据失败: {symbol} - {e}")
            return None
    
    @cached(ttl=600, key_prefix="stock_batch")
    @monitor_performance
    def get_stock_daily_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, pl.DataFrame]:
        """
        批量获取股票数据
        
        使用并行查询提高效率
        """
        results = {}
        
        def query_single(symbol: str) -> Tuple[str, Optional[pl.DataFrame]]:
            df = self.get_stock_daily(symbol, start_date, end_date, fields)
            return symbol, df
        
        # 并行查询
        futures = [self._executor.submit(query_single, s) for s in symbols]
        
        for future in futures:
            symbol, df = future.result()
            if df is not None:
                results[symbol] = df
        
        return results
    
    # ========================================================================
    # 2. 股票池查询 (高频缓存)
    # ========================================================================
    
    @cached(ttl=3600, key_prefix="stock_pool")
    @monitor_performance
    def get_stock_pool(self, date: str) -> Optional[pl.DataFrame]:
        """
        获取指定日期的股票池
        
        高频查询，使用长缓存时间
        """
        try:
            from data_svc.database.polars_data_loader_v4 import PolarsDataLoaderV4
            
            loader = PolarsDataLoaderV4()
            info_path = loader.parquet_dir / "stock_info.parquet"
            
            if not info_path.exists():
                return None
            
            df_info = pl.read_parquet(info_path)
            
            # 过滤已上市股票
            df_info = df_info.filter(
                (pl.col('list_date').is_null()) | (pl.col('list_date') <= date)
            )
            
            return df_info
            
        except Exception as e:
            self.logger.error(f"[DataService] 获取股票池失败: {e}")
            return None
    
    # ========================================================================
    # 3. 交易日历查询 (永久缓存)
    # ========================================================================
    
    @cached(ttl=None, key_prefix="trading_dates")
    @monitor_performance
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日历
        
        交易日历不常变化，使用永久缓存
        """
        try:
            from data_svc.database.polars_data_loader_v4 import PolarsDataLoaderV4
            
            loader = PolarsDataLoaderV4()
            daily_path = loader.parquet_dir / "stock_daily.parquet"
            
            if not daily_path.exists():
                return []
            
            # 使用 scan_parquet 高效获取日期
            lf = pl.scan_parquet(daily_path)
            lf = lf.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date)
            )
            lf = lf.select('trade_date').unique().sort()
            
            df = lf.collect()
            
            if df.is_empty():
                return []
            
            return df['trade_date'].to_list()
            
        except Exception as e:
            self.logger.error(f"[DataService] 获取交易日历失败: {e}")
            return []
    
    # ========================================================================
    # 4. 最新价格查询 (短缓存)
    # ========================================================================
    
    @cached(ttl=60, key_prefix="latest_price")
    @monitor_performance
    def get_latest_price(self, symbol: str, date: Optional[str] = None) -> Optional[Dict]:
        """
        获取最新价格
        
        价格数据变化频繁，使用短缓存
        """
        try:
            if date is None:
                # 获取最近交易日
                dates = self.get_trading_dates("2020-01-01", "2099-12-31")
                if not dates:
                    return None
                date = dates[-1]
            
            df = self.get_stock_daily(symbol, date, date, ['close', 'volume', 'amount'])
            
            if df is None or df.is_empty():
                return None
            
            row = df.row(0, named=True)
            
            return {
                'symbol': symbol,
                'date': date,
                'price': row.get('close', 0),
                'volume': row.get('volume', 0),
                'amount': row.get('amount', 0)
            }
            
        except Exception as e:
            self.logger.error(f"[DataService] 获取最新价格失败: {symbol} - {e}")
            return None
    
    # ========================================================================
    # 5. 数据矩阵加载 (高性能)
    # ========================================================================
    
    @cached(ttl=180, key_prefix="data_matrix")
    @monitor_performance
    def load_data_matrix(
        self,
        start_date: str,
        end_date: str,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        加载数据矩阵
        
        用于向量化回测计算
        """
        try:
            from data_svc.database.polars_data_loader_v4 import PolarsDataLoaderV4
            
            loader = PolarsDataLoaderV4()
            return loader.load_period_to_matrix(start_date, end_date, fields)
            
        except Exception as e:
            self.logger.error(f"[DataService] 加载数据矩阵失败: {e}")
            return None
    
    # ========================================================================
    # 6. 预加载热点数据
    # ========================================================================
    
    def preload_hot_data(self) -> Dict[str, Any]:
        """
        预加载热点数据
        
        在系统启动时调用，加速后续查询
        """
        if self._preloaded:
            return {"status": "already_preloaded"}
        
        start_time = time.perf_counter()
        results = {}
        
        try:
            # 1. 预加载股票信息
            self.logger.info("[DataService] 预加载股票信息...")
            from data_svc.database.polars_data_loader_v4 import PolarsDataLoaderV4
            loader = PolarsDataLoaderV4()
            info_path = loader.parquet_dir / "stock_info.parquet"
            
            if info_path.exists():
                df_info = pl.read_parquet(info_path)
                with self._cache_lock:
                    self._hot_data_cache['stock_info'] = df_info
                results['stock_info'] = {"status": "success", "count": len(df_info)}
            
            # 2. 预加载最近交易日
            self.logger.info("[DataService] 预加载交易日历...")
            dates = self.get_trading_dates("2024-01-01", "2025-12-31")
            results['trading_dates'] = {"status": "success", "count": len(dates)}
            
            # 3. 预加载指数数据
            self.logger.info("[DataService] 预加载指数数据...")
            index_path = loader.parquet_dir / "index_daily.parquet"
            if index_path.exists():
                df_index = pl.read_parquet(index_path)
                with self._cache_lock:
                    self._hot_data_cache['index_daily'] = df_index
                results['index_daily'] = {"status": "success", "count": len(df_index)}
            
            self._preloaded = True
            
            duration = (time.perf_counter() - start_time) * 1000
            self.logger.info(f"[DataService] 预加载完成，耗时 {duration:.2f}ms")
            
            return {
                "status": "success",
                "total_time_ms": round(duration, 2),
                "tasks": results
            }
            
        except Exception as e:
            self.logger.error(f"[DataService] 预加载失败: {e}")
            return {"status": "error", "error": str(e)}
    
    # ========================================================================
    # 7. 缓存管理
    # ========================================================================
    
    def clear_cache(self) -> None:
        """清除缓存"""
        _global_cache.clear()
        with self._cache_lock:
            self._hot_data_cache.clear()
        self.logger.info("[DataService] 缓存已清除")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        from server.performance_optimizer import get_performance_stats
        
        stats = get_performance_stats()
        
        with self._cache_lock:
            stats['hot_data_cache'] = {
                "size": len(self._hot_data_cache),
                "keys": list(self._hot_data_cache.keys())
            }
        
        return stats
    
    # ========================================================================
    # 8. 批量价格查询 (用于持仓面板)
    # ========================================================================
    
    @monitor_performance
    def get_latest_prices_batch(
        self,
        symbols: List[str],
        date: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        批量获取最新价格
        
        用于持仓面板等需要同时查询多个股票价格的场景
        """
        results = {}
        
        # 先去重
        unique_symbols = list(set(symbols))
        
        # 并行查询
        def query_price(symbol: str) -> Tuple[str, Optional[Dict]]:
            price_data = self.get_latest_price(symbol, date)
            return symbol, price_data
        
        futures = [self._executor.submit(query_price, s) for s in unique_symbols]
        
        for future in futures:
            symbol, data = future.result()
            if data:
                results[symbol] = data
        
        return results


# 全局服务实例
def get_optimized_data_service() -> OptimizedDataService:
    """获取优化数据服务实例"""
    return OptimizedDataService()


# 便捷函数
def get_stock_data_cached(
    symbol: str,
    start_date: str,
    end_date: str,
    fields: Optional[List[str]] = None
) -> Optional[pl.DataFrame]:
    """获取股票数据 (带缓存)"""
    service = get_optimized_data_service()
    return service.get_stock_daily(symbol, start_date, end_date, fields)


def get_latest_prices_cached(
    symbols: List[str],
    date: Optional[str] = None
) -> Dict[str, Dict]:
    """批量获取最新价格 (带缓存)"""
    service = get_optimized_data_service()
    return service.get_latest_prices_batch(symbols, date)
