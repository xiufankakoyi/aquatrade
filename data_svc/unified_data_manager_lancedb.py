"""
统一数据管理器 (LanceDB 版)
==========================

替代 ArcticDB 版本，使用 LanceDB 作为底层存储。

架构:
┌─────────────────────────────────────────────────────────────────┐
│                    生产级数据架构（LanceDB）                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  【单一存储：LanceDB】                                            │
│  Tushare → Polars → Arrow Table → LanceDB                       │
│                                  ↓                              │
│                        支持增量写入、向量检索                      │
│                                                                 │
│  【读取加速：内存缓存】（核心优化点）                              │
│  服务启动: LanceDB → Arrow → Polars → 内存字典                  │
│  回测执行: 内存字典 → 零拷贝查询（无磁盘IO）                       │
│                                                                 │
│  【灾难恢复】（按需导出，非实时双写）                              │
│  定期: LanceDB → 导出Parquet → 异地备份                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

关键特性:
- LanceDB 原生支持 Arrow，零拷贝读写
- 支持增量写入、向量检索、多模态存储
- 使用 scanner(columns=...) 指定列读取，性能优于 Parquet
"""
import os
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl
import pyarrow as pa
from loguru import logger

from data_svc.storage.lancedb_manager import get_lancedb_manager
from data_svc.storage.lancedb_reader import get_lancedb_reader


@dataclass
class WriteResult:
    """写入结果"""
    success: bool
    symbol: str
    rows: int = 0
    version: Optional[int] = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class UnifiedDataManager:
    """
    统一数据管理器 (LanceDB 版)
    
    单一存储: LanceDB (Arrow 原生支持)
    读取加速: 内存缓存
    
    使用示例:
        >>> manager = UnifiedDataManager()
        >>> 
        >>> # 写入数据
        >>> df_pl = pl.DataFrame({...})
        >>> result = manager.write('daily', 'daily_2024-01-15', df_pl)
        >>> 
        >>> # 预加载到内存
        >>> manager.preload_to_memory(years=2)
        >>> 
        >>> # 读取数据 (优先内存缓存)
        >>> df = manager.read('daily', start_date='2024-01-01', end_date='2024-03-31')
    """
    
    LIBRARIES = {
        'daily': '股票日线数据',
        'stock_info': '股票基本信息',
        'benchmark_daily': '指数日线数据',
        'limit_status': '涨跌停状态',
        'factor': '因子数据',
    }
    
    HOT_DATA_YEARS = 2
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        初始化
        
        Args:
            db_path: LanceDB 数据库路径 (默认: data/lancedb)
            progress_callback: 进度回调函数
        """
        self._manager = get_lancedb_manager(db_path)
        self._reader = get_lancedb_reader(db_path)
        self.progress_callback = progress_callback
        
        self._memory_cache: Dict[str, Dict[str, pl.DataFrame]] = {
            lib: {} for lib in self.LIBRARIES
        }
        self._cache_loaded = False
        self._preloaded_date_range: Optional[tuple] = None
        
        logger.info(f"[UnifiedDataManager] 已连接 LanceDB: {self._manager.db_path}")
    
    def _emit_progress(self, stage: str, progress: float, message: str):
        """发送进度更新"""
        if self.progress_callback:
            self.progress_callback({
                "stage": stage,
                "progress": progress,
                "message": message,
                "timestamp": time.time()
            })
    
    def preprocess_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        预处理 DataFrame
        
        1. 字符串清理
        2. 类型优化
        """
        if df.is_empty():
            return df
        
        for col in df.columns:
            dtype = df[col].dtype
            
            if dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col(col).str.strip_chars().alias(col)
                )
            elif dtype == pl.Int64:
                if df[col].null_count() == 0:
                    min_val, max_val = df[col].min(), df[col].max()
                    if min_val >= -2147483648 and max_val <= 2147483647:
                        df = df.with_columns(pl.col(col).cast(pl.Int32))
        
        return df
    
    def write(
        self,
        library: str,
        symbol: str,
        df: pl.DataFrame,
        metadata: Optional[Dict] = None
    ) -> WriteResult:
        """
        写入数据 (零拷贝)
        
        Args:
            library: 库名 (daily, stock_info, etc.)
            symbol: 数据符号
            df: Polars DataFrame
            metadata: 元数据
            
        Returns:
            WriteResult
        """
        t0 = time.perf_counter()
        
        try:
            df = self.preprocess_dataframe(df)
            rows = len(df)
            
            if library not in self.LIBRARIES:
                raise ValueError(f"Unknown library: {library}")
            
            rows_written = self._manager.write_daily_data(df, mode="upsert")
            
            elapsed_ms = (time.perf_counter() - t0) * 1000
            
            logger.debug(f"[LanceDB] 写入 {library}/{symbol}: {rows} 行, 耗时 {elapsed_ms:.2f}ms")
            
            return WriteResult(
                success=True,
                symbol=symbol,
                rows=rows_written,
                elapsed_ms=elapsed_ms
            )
            
        except Exception as e:
            logger.error(f"[UnifiedDataManager] 写入失败: {e}")
            return WriteResult(
                success=False,
                symbol=symbol,
                error=str(e),
                elapsed_ms=(time.perf_counter() - t0) * 1000
            )
    
    def append(
        self,
        library: str,
        symbol: str,
        df: pl.DataFrame
    ) -> WriteResult:
        """
        追加数据
        
        Args:
            library: 库名
            symbol: 数据符号
            df: Polars DataFrame
            
        Returns:
            WriteResult
        """
        t0 = time.perf_counter()
        
        try:
            df = self.preprocess_dataframe(df)
            rows = len(df)
            
            rows_written = self._manager.write_daily_data(df, mode="append")
            
            elapsed_ms = (time.perf_counter() - t0) * 1000
            
            logger.debug(f"[LanceDB] 追加 {library}/{symbol}: {rows} 行")
            
            return WriteResult(
                success=True,
                symbol=symbol,
                rows=rows_written,
                elapsed_ms=elapsed_ms
            )
            
        except Exception as e:
            logger.error(f"[UnifiedDataManager] 追加失败: {e}")
            return WriteResult(
                success=False,
                symbol=symbol,
                error=str(e),
                elapsed_ms=(time.perf_counter() - t0) * 1000
            )
    
    def read(
        self,
        library: str,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pl.DataFrame:
        """
        读取数据 (零拷贝)
        
        Args:
            library: 库名
            symbol: 数据符号 (可选，LanceDB 中忽略此参数)
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用内存缓存
            
        Returns:
            Polars DataFrame
        """
        if library not in self.LIBRARIES:
            raise ValueError(f"Unknown library: {library}")
        
        if use_cache and self._cache_loaded:
            cache_key = f"{library}_{start_date}_{end_date}"
            if cache_key in self._memory_cache.get(library, {}):
                logger.debug(f"[UnifiedDataManager] 内存缓存命中: {cache_key}")
                return self._memory_cache[library][cache_key].clone()
        
        try:
            df = self._reader.read_all(start_date, end_date)
            
            if use_cache:
                cache_key = f"{library}_{start_date}_{end_date}"
                if library not in self._memory_cache:
                    self._memory_cache[library] = {}
                self._memory_cache[library][cache_key] = df.clone()
            
            return df
            
        except Exception as e:
            logger.warning(f"[UnifiedDataManager] 读取失败: {e}")
            return pl.DataFrame()
    
    def preload_to_memory(
        self,
        years: int = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, pl.DataFrame]:
        """
        预加载数据到内存
        
        服务启动时调用，将热数据加载到内存缓存
        
        Args:
            years: 预加载年数 (默认: HOT_DATA_YEARS)
            start_date: 开始日期 (可选)
            end_date: 结束日期 (可选)
            
        Returns:
            Dict[str, pl.DataFrame] 预加载的数据
        """
        years = years or self.HOT_DATA_YEARS
        
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"[UnifiedDataManager] 预加载数据到内存: {start_date} ~ {end_date}")
        t0 = time.perf_counter()
        
        result = {}
        
        df = self._reader.read_all(start_date, end_date)
        
        if not df.is_empty():
            result['daily'] = df
            
            cache_key = f"daily_{start_date}_{end_date}"
            self._memory_cache['daily'][cache_key] = df.clone()
            
            logger.debug(f"[UnifiedDataManager] 预加载 daily: {len(df)} 行")
        
        self._preloaded_date_range = (start_date, end_date)
        self._cache_loaded = True
        
        elapsed = time.perf_counter() - t0
        total_rows = sum(len(df) for df in result.values())
        logger.info(f"[UnifiedDataManager] 预加载完成: {total_rows} 行, 耗时 {elapsed:.2f}s")
        
        return result
    
    def get_preloaded_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, pl.DataFrame]:
        """
        获取预加载的数据（从内存缓存）
        
        Args:
            start_date: 开始日期 (可选)
            end_date: 结束日期 (可选)
            
        Returns:
            Dict[str, pl.DataFrame] 各库的预加载数据
        """
        result = {}
        
        for library in ['daily']:
            if library in self._memory_cache:
                for cache_key, df in self._memory_cache[library].items():
                    if not df.is_empty():
                        if start_date and end_date:
                            date_col = 'trade_date' if 'trade_date' in df.columns else 'date'
                            if date_col in df.columns:
                                date_dtype = df.schema[date_col]
                                if date_dtype in [pl.Date, pl.Datetime]:
                                    df = df.filter(
                                        (pl.col(date_col) >= pl.lit(start_date).str.to_date()) &
                                        (pl.col(date_col) <= pl.lit(end_date).str.to_date())
                                    )
                                else:
                                    df = df.filter(
                                        (pl.col(date_col) >= start_date) &
                                        (pl.col(date_col) <= end_date)
                                    )
                        
                        if library not in result:
                            result[library] = df
        
        return result
    
    def export_to_parquet(
        self,
        library: str,
        output_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> bool:
        """
        导出为 Parquet (用于异地备份)
        
        Args:
            library: 库名
            output_path: 输出路径
            start_date: 开始日期 (可选)
            end_date: 结束日期 (可选)
            
        Returns:
            bool 是否成功
        """
        try:
            df = self.read(library, start_date=start_date, end_date=end_date, use_cache=False)
            if df.is_empty():
                logger.warning(f"[UnifiedDataManager] 无数据可导出: {library}")
                return False
            
            df.write_parquet(output_path)
            logger.info(f"[UnifiedDataManager] 导出 {library} 到 {output_path}: {len(df)} 行")
            return True
            
        except Exception as e:
            logger.error(f"[UnifiedDataManager] 导出失败: {e}")
            return False
    
    def clear_memory_cache(self):
        """清除内存缓存"""
        self._memory_cache = {lib: {} for lib in self.LIBRARIES}
        self._cache_loaded = False
        self._preloaded_date_range = None
        self._reader.clear_cache()
        logger.info("[UnifiedDataManager] 内存缓存已清除")
    
    def get_trading_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """
        获取交易日列表

        Args:
            start_date: 开始日期 (可选，格式: YYYY-MM-DD)
            end_date: 结束日期 (可选，格式: YYYY-MM-DD)

        Returns:
            日期字符串列表 (格式: YYYY-MM-DD)，按升序排列
        """
        try:
            dates = self._reader.list_dates()
            
            if start_date or end_date:
                dates = [
                    d for d in dates
                    if (not start_date or d >= start_date) and
                       (not end_date or d <= end_date)
                ]
            
            return dates
            
        except Exception as e:
            logger.warning(f"[UnifiedDataManager] 获取交易日失败: {e}")
            return []
    
    def get_stock_pool(
        self,
        date_str: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pl.DataFrame:
        """
        获取某日的股票池 (Polars 格式)

        Args:
            date_str: 日期 (YYYY-MM-DD)
            filters: 可选的过滤条件

        Returns:
            Polars DataFrame
        """
        try:
            df = self._reader.read_all(date_str, date_str)
            
            if filters and not df.is_empty():
                df = self._apply_filters(df, filters)
            
            return df

        except Exception as e:
            logger.warning(f"[UnifiedDataManager] 获取股票池失败 {date_str}: {e}")
            return pl.DataFrame()
    
    def get_stock_pool_at_time(
        self,
        timestamp: Union[str, datetime, pd.Timestamp]
    ) -> pd.DataFrame:
        """
        获取某时间点的股票池 (Pandas 格式，兼容旧接口)

        Args:
            timestamp: 时间戳

        Returns:
            Pandas DataFrame
        """
        if isinstance(timestamp, (datetime, pd.Timestamp)):
            date_str = timestamp.strftime('%Y-%m-%d')
        else:
            date_str = str(timestamp)[:10]

        df = self.get_stock_pool(date_str)
        return df.to_pandas() if not df.is_empty() else pd.DataFrame()
    
    def _apply_filters(
        self,
        df: pl.DataFrame,
        filters: Dict[str, Any]
    ) -> pl.DataFrame:
        """应用过滤条件"""
        for col, condition in filters.items():
            if col in df.columns:
                if isinstance(condition, tuple):
                    min_val, max_val = condition
                    df = df.filter(
                        (pl.col(col) >= min_val) & (pl.col(col) <= max_val)
                    )
                elif isinstance(condition, list):
                    df = df.filter(pl.col(col).is_in(condition))
                else:
                    df = df.filter(pl.col(col) == condition)
        return df
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        reader_stats = self._reader.get_stats()
        manager_stats = self._manager.get_stats()
        
        return {
            **reader_stats,
            **manager_stats,
            'cache_loaded': self._cache_loaded,
            'preloaded_date_range': self._preloaded_date_range,
        }


_global_manager: Optional[UnifiedDataManager] = None


def get_unified_manager(**kwargs) -> UnifiedDataManager:
    """获取全局 UnifiedDataManager 实例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = UnifiedDataManager(**kwargs)
        logger.info(f"[UnifiedDataManager] 创建全局实例, cache_loaded={_global_manager._cache_loaded}")
    else:
        logger.info(f"[UnifiedDataManager] 复用全局实例, cache_loaded={_global_manager._cache_loaded}, range={_global_manager._preloaded_date_range}")
    return _global_manager


if __name__ == "__main__":
    print("=" * 60)
    print("统一数据管理器测试 (LanceDB 版)")
    print("=" * 60)
    
    manager = UnifiedDataManager()
    
    print("\n读取测试...")
    df = manager.read('daily', start_date='2024-01-01', end_date='2024-01-31')
    print(f"读取: {len(df)} 行")
    
    print("\n预加载测试...")
    manager.preload_to_memory(years=1)
    
    print("\n测试完成!")
