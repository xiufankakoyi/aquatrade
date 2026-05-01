"""
统一数据查询适配器 (LanceDB 版本)

为 signal_engine 等模块提供统一的数据查询接口。
使用 LanceDB 作为底层存储。
"""

from typing import Optional, List, Dict, Any, Set
import pandas as pd
import polars as pl
from loguru import logger
import time
import os
from pathlib import Path

try:
    from data_svc.storage.lancedb_reader import LanceDBDataReader, get_lancedb_reader
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

PROJECT_ROOT = Path(__file__).parent.parent

_stock_basic_cache = None
_fund_basic_cache = None
_libraries_cache = None
_symbols_cache = {}
_cache_timestamp = 0
_CACHE_TTL = 300


def _invalidate_cache_if_needed():
    """检查缓存是否过期，如果过期则清除"""
    global _libraries_cache, _symbols_cache, _cache_timestamp
    current_time = time.time()
    if current_time - _cache_timestamp > _CACHE_TTL:
        _libraries_cache = None
        _symbols_cache = {}
        _cache_timestamp = current_time


def get_libraries_cached() -> Set[str]:
    """获取库列表（带缓存）"""
    global _libraries_cache
    _invalidate_cache_if_needed()

    if _libraries_cache is None:
        lancedb_path = PROJECT_ROOT / 'data' / 'lancedb'
        if lancedb_path.exists():
            _libraries_cache = set(d.name for d in lancedb_path.iterdir() if d.is_dir())
        else:
            _libraries_cache = set()
    return _libraries_cache


def _convert_to_polars(data) -> pl.DataFrame:
    """将数据转换为 Polars DataFrame"""
    if data is None:
        return pl.DataFrame()
    if isinstance(data, pl.DataFrame):
        return data
    if hasattr(data, 'to_polars'):
        return data.to_polars()
    if hasattr(data, 'to_arrow'):
        return pl.from_arrow(data.to_arrow())
    if isinstance(data, pd.DataFrame):
        return pl.from_pandas(data)
    return pl.DataFrame(data)


class UnifiedDataQuery:
    """
    统一数据查询接口 (LanceDB 版本)

    为回测、筛选等模块提供统一的数据查询能力。
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(PROJECT_ROOT / 'data' / 'lancedb')
        self._reader = None

    @property
    def reader(self) -> Optional[LanceDBDataReader]:
        """获取 LanceDB Reader"""
        if self._reader is None and LANCEDB_AVAILABLE:
            self._reader = get_lancedb_reader(self.db_path)
        return self._reader

    def get_stock_history(
        self,
        symbol: str,
        start: str,
        end: str,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取股票历史数据"""
        if not self.reader:
            logger.warning("[UnifiedDataQuery] LanceDB not available")
            return pd.DataFrame()

        try:
            df = self.reader.read(symbol, start, end)
            if df.is_empty():
                return pd.DataFrame()

            if columns:
                available_cols = [c for c in columns if c in df.columns]
                df = df.select(available_cols)

            return df.to_pandas()
        except Exception as e:
            logger.error(f"[UnifiedDataQuery] Error reading {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基本信息"""
        global _stock_basic_cache

        if _stock_basic_cache is not None:
            return _stock_basic_cache

        if not self.reader:
            return pd.DataFrame()

        try:
            df = self.reader.read("stock_info", "1900-01-01", "2100-12-31")
            if df.is_empty():
                return pd.DataFrame()
            _stock_basic_cache = df.to_pandas()
            return _stock_basic_cache
        except Exception as e:
            logger.warning(f"[UnifiedDataQuery] stock_basic error: {e}")
            return pd.DataFrame()

    def get_index_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """获取指数日线数据"""
        if not self.reader:
            return pd.DataFrame()

        try:
            df = self.reader.read(symbol, start, end, table_name="index_daily")
            if df.is_empty():
                return pd.DataFrame()
            return df.to_pandas()
        except Exception as e:
            logger.warning(f"[UnifiedDataQuery] index_daily error: {e}")
            return pd.DataFrame()

    def get_fund_nav(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """获取基金净值数据"""
        if not self.reader:
            return pd.DataFrame()

        try:
            df = self.reader.read(symbol, start, end, table_name="fund_nav")
            if df.is_empty():
                return pd.DataFrame()
            return df.to_pandas()
        except Exception as e:
            logger.warning(f"[UnifiedDataQuery] fund_nav error: {e}")
            return pd.DataFrame()

    def get_trade_dates(self, start: str, end: str) -> List[str]:
        """获取交易日期列表"""
        if not self.reader:
            return []

        try:
            df = self.reader.read_all(table_name="daily_ohlcv", start=start, end=end)
            if df.is_empty():
                return []

            if 'trade_date' in df.columns:
                dates = df['trade_date'].unique().sort().to_list()
                return [str(d)[:10] for d in dates]
            return []
        except Exception as e:
            logger.warning(f"[UnifiedDataQuery] trade_dates error: {e}")
            return []

    def list_symbols(self, table_name: str = "daily_ohlcv") -> List[str]:
        """获取所有股票代码"""
        if not self.reader:
            return []

        try:
            return self.reader.list_symbols(table_name)
        except Exception as e:
            logger.warning(f"[UnifiedDataQuery] list_symbols error: {e}")
            return []


_unified_data_query_instance: Optional[UnifiedDataQuery] = None


def get_unified_data_query(db_path: Optional[str] = None) -> UnifiedDataQuery:
    """获取统一数据查询单例"""
    global _unified_data_query_instance
    if _unified_data_query_instance is None:
        _unified_data_query_instance = UnifiedDataQuery(db_path)
    return _unified_data_query_instance


def reset_unified_data_query():
    """重置单例"""
    global _unified_data_query_instance, _stock_basic_cache, _fund_basic_cache
    _unified_data_query_instance = None
    _stock_basic_cache = None
    _fund_basic_cache = None
