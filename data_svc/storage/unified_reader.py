"""
LanceDB 读取层
==============

替代 ArcticDB 的 UnifiedDataReader，提供统一的读取接口。

核心特性:
1. 索引加速: 利用 LanceDB 标量索引加速日期范围查询
2. 零拷贝: Arrow Table -> Polars DataFrame
3. COW 包装器: Copy-On-Write，避免不必要的数据复制
4. 读写锁分离: 提高并发读取性能
5. 兼容接口: 与 UnifiedDataReader 接口兼容

性能说明:
- 使用 scanner(columns=...) 指定列读取，性能优于 Parquet
- 全量读取所有列时较慢，建议只读取必要列
- 优势: 支持增量写入、向量检索、多模态存储

架构位置:
┌─────────────────────────────────────────────────────────────┐
│                    LanceDBDataReader                        │
│  - read(symbols, start, end, fields, filters)              │
│  - 返回 Polars DataFrame                                    │
│  - 使用 to_lance() + scanner 优化性能                        │
│  - COW 包装器 + 读写锁分离                                   │
└─────────────────────────────────────────────────────────────┘
"""

from typing import Optional, List, Union, Dict, Any, Tuple
from datetime import datetime, date
from collections import OrderedDict
import threading
import time
import polars as pl
import pyarrow as pa
from loguru import logger
from pathlib import Path

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False


DEFAULT_OHLCV_COLUMNS = [
    'stock_code', 'trade_date', 
    'open', 'high', 'low', 'close', 'volume', 'amount'
]


class ReadWriteLock:
    """
    读写锁实现
    
    允许多个读取器同时访问，但写入器独占访问。
    适用于读多写少的场景。
    
    使用示例:
        >>> rwlock = ReadWriteLock()
        >>> 
        >>> # 读取操作
        >>> with rwlock.read_lock():
        >>>     data = cache.get(key)
        >>> 
        >>> # 写入操作
        >>> with rwlock.write_lock():
        >>>     cache.set(key, value)
    """
    
    def __init__(self):
        self._readers = 0
        self._writers_waiting = 0
        self._writing = False
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._write_ready = threading.Condition(self._lock)
    
    def acquire_read(self):
        """获取读锁"""
        with self._lock:
            while self._writing or self._writers_waiting > 0:
                self._read_ready.wait()
            self._readers += 1
    
    def release_read(self):
        """释放读锁"""
        with self._lock:
            self._readers -= 1
            if self._readers == 0:
                self._write_ready.notify()
    
    def acquire_write(self):
        """获取写锁"""
        with self._lock:
            self._writers_waiting += 1
            while self._readers > 0 or self._writing:
                self._write_ready.wait()
            self._writers_waiting -= 1
            self._writing = True
    
    def release_write(self):
        """释放写锁"""
        with self._lock:
            self._writing = False
            self._read_ready.notify_all()
            self._write_ready.notify()
    
    def read_lock(self):
        """返回读锁上下文管理器"""
        return _ReadLockContext(self)
    
    def write_lock(self):
        """返回写锁上下文管理器"""
        return _WriteLockContext(self)


class _ReadLockContext:
    """读锁上下文管理器"""
    
    def __init__(self, rwlock: ReadWriteLock):
        self._rwlock = rwlock
    
    def __enter__(self):
        self._rwlock.acquire_read()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rwlock.release_read()
        return False


class _WriteLockContext:
    """写锁上下文管理器"""
    
    def __init__(self, rwlock: ReadWriteLock):
        self._rwlock = rwlock
    
    def __enter__(self):
        self._rwlock.acquire_write()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rwlock.release_write()
        return False


class COWDataFrame:
    """
    Copy-On-Write DataFrame 包装器
    
    Polars DataFrame 本身是不可变的，clone() 是零拷贝的引用计数增加。
    这个包装器提供了显式的 COW 语义和引用追踪。
    
    使用示例:
        >>> cow_df = COWDataFrame(pl.DataFrame({...}))
        >>> 
        >>> # 读取：零拷贝引用
        >>> df = cow_df.read()
        >>> 
        >>> # 写入：创建新实例
        >>> cow_df = cow_df.write(new_df)
    """
    
    __slots__ = ('_df', '_ref_count', '_lock')
    
    def __init__(self, df: pl.DataFrame):
        self._df = df
        self._ref_count = 0
        self._lock = threading.Lock()
    
    def read(self) -> pl.DataFrame:
        """
        读取数据（零拷贝引用）
        
        Polars 的 clone() 是 O(1) 操作，只增加引用计数。
        
        Returns:
            DataFrame 的零拷贝引用
        """
        with self._lock:
            self._ref_count += 1
            return self._df.clone()
    
    def release(self) -> None:
        """释放引用"""
        with self._lock:
            if self._ref_count > 0:
                self._ref_count -= 1
    
    def write(self, new_df: pl.DataFrame) -> 'COWDataFrame':
        """
        写入数据（创建新实例）
        
        Args:
            new_df: 新的 DataFrame
            
        Returns:
            新的 COWDataFrame 实例
        """
        return COWDataFrame(new_df)
    
    def get_ref_count(self) -> int:
        """获取当前引用计数"""
        with self._lock:
            return self._ref_count
    
    def is_shared(self) -> bool:
        """是否被多个引用共享"""
        with self._lock:
            return self._ref_count > 1
    
    @property
    def df(self) -> pl.DataFrame:
        """直接访问内部 DataFrame（不增加引用计数）"""
        return self._df
    
    def __len__(self) -> int:
        return len(self._df)
    
    def is_empty(self) -> bool:
        return self._df.is_empty()


class LanceDBDataReader:
    """
    LanceDB 读取层
    
    为回测和筛选模块提供统一的底层读取能力。
    使用 to_lance() + scanner 方法优化读取性能。
    
    特性:
    - COW 包装器：避免不必要的数据复制
    - 读写锁分离：提高并发读取性能
    - LRU 缓存：内存可控的缓存机制
    
    使用示例:
        >>> reader = LanceDBDataReader()
        >>> 
        >>> # 单股票读取
        >>> df = reader.read("000001.SZ", "2024-01-01", "2024-12-31")
        >>> 
        >>> # 多股票读取
        >>> df = reader.read(["000001.SZ", "000002.SZ"], "2024-01-01", "2024-12-31")
        >>> 
        >>> # 全市场读取
        >>> df = reader.read(None, "2024-01-01", "2024-12-31")
    """
    
    TABLE_NAME = "daily_ohlcv"
    
    def __init__(self, db_path: Optional[str] = None, library_name: str = None):
        """
        初始化读取器
        
        Args:
            db_path: 数据库路径
            library_name: 兼容参数，忽略
        """
        if not LANCEDB_AVAILABLE:
            raise ImportError("LanceDB is required. Install with: pip install lancedb")
        
        if db_path is None:
            from config.config import Config
            db_path = getattr(Config, 'LANCEDB_PATH', None)
            if db_path is None:
                project_root = Path(__file__).parent.parent.parent
                db_path = str(project_root / "data" / "lancedb")
        
        self.db_path = db_path
        self.library_name = library_name or self.TABLE_NAME
        self._db = None
        self._table = None
        self._lance_ds = None
        
        self._memory_cache: OrderedDict[str, COWDataFrame] = OrderedDict()
        self._rwlock = ReadWriteLock()
        self._max_cache_size_mb = 2048
        self._current_cache_size_mb = 0.0
        
        self._query_count = 0
        self._cache_hits = 0
    
    def _connect(self) -> None:
        """建立连接"""
        if self._db is None:
            self._db = lancedb.connect(self.db_path)
    
    @property
    def table(self):
        """获取表实例（延迟加载）"""
        if self._table is None:
            self._connect()
            if self.TABLE_NAME in self._db.table_names():
                self._table = self._db.open_table(self.TABLE_NAME)
        return self._table
    
    @property
    def lance_ds(self):
        """获取 Lance Dataset 实例（用于高性能读取）"""
        if self._lance_ds is None:
            if self.table is not None:
                self._lance_ds = self.table.to_lance()
        return self._lance_ds
    
    @property
    def library(self):
        """兼容属性：返回 table"""
        return self.table
    
    def _estimate_size_mb(self, df: pl.DataFrame) -> float:
        if df is None or df.is_empty():
            return 0.0
        return df.estimated_size() / (1024 * 1024)
    
    def _evict_lru(self, needed_mb: float) -> None:
        """LRU 淘汰策略"""
        with self._rwlock.write_lock():
            while self._current_cache_size_mb + needed_mb > self._max_cache_size_mb and self._memory_cache:
                key, cow_df = self._memory_cache.popitem(last=False)
                self._current_cache_size_mb -= self._estimate_size_mb(cow_df.df)
                logger.debug(f"[LanceDBDataReader] LRU 淘汰: {key}")
    
    def set_cache_limit(self, max_size_mb: int) -> None:
        """设置缓存限制"""
        with self._rwlock.write_lock():
            self._max_cache_size_mb = max_size_mb
            if self._current_cache_size_mb > max_size_mb:
                self._evict_lru(0)
    
    def get_cache_size_mb(self) -> float:
        """获取缓存大小"""
        with self._rwlock.read_lock():
            return self._current_cache_size_mb
    
    def clear_cache(self) -> None:
        """清空缓存"""
        with self._rwlock.write_lock():
            self._memory_cache.clear()
            self._current_cache_size_mb = 0.0
    
    def _get_date_column(self, df: pl.DataFrame) -> Optional[str]:
        """获取日期列名"""
        date_columns = ["trade_date", "date", "timestamp", "datetime"]
        for col in date_columns:
            if col in df.columns:
                return col
        return None
    
    def _make_chunk_key(self, symbol: str, date_str: str) -> str:
        """兼容方法：生成缓存 key"""
        if isinstance(date_str, str) and len(date_str) >= 7:
            return f"{symbol}_{date_str[:7]}"
        return f"{symbol}_{date_str}"
    
    def _parse_chunk_key(self, key: str) -> Tuple[str, str]:
        """兼容方法：解析缓存 key"""
        parts = key.rsplit('_', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return key, ""
    
    def _get_months_in_range(self, start_date: str, end_date: str) -> List[str]:
        """兼容方法：获取日期范围内的所有月份"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        months = []
        current = start
        while current <= end:
            months.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return months
    
    def _make_cache_key(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str],
        end_date: Optional[str],
        fields: Optional[List[str]] = None,
    ) -> str:
        """生成缓存 key"""
        if symbols is None:
            sym_str = "all"
        elif isinstance(symbols, str):
            sym_str = symbols
        else:
            sym_str = f"batch_{len(symbols)}"
        
        fields_str = ",".join(sorted(fields)) if fields else "all"
        return f"{sym_str}_{start_date or 'min'}_{end_date or 'max'}_{fields_str}"
    
    def _build_filters(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[str]:
        """构建过滤条件"""
        filters = []
        
        if start_date:
            filters.append(f"trade_date >= date '{start_date}'")
        
        if end_date:
            filters.append(f"trade_date <= date '{end_date}'")
        
        if symbols is not None:
            if isinstance(symbols, str):
                filters.append(f'stock_code = \'{symbols}\'')
            elif len(symbols) == 1:
                filters.append(f'stock_code = \'{symbols[0]}\'')
            elif len(symbols) <= 100:
                quoted = [f'\'{s}\'' for s in symbols]
                filters.append(f'stock_code IN ({", ".join(quoted)})')
        
        return filters
    
    def read(
        self,
        symbols: Union[str, List[str], None],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        as_of: Optional[datetime] = None,
    ) -> pl.DataFrame:
        """
        统一的底层读取方法
        
        Args:
            symbols: 股票代码或代码列表，None 表示全部股票
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            fields: 要读取的字段列表（可选，默认读取 OHLCV）
            as_of: 兼容参数，忽略
            
        Returns:
            Polars DataFrame（零拷贝引用）
            
        Example:
            >>> reader = LanceDBDataReader()
            >>> df = reader.read("000001.SZ", "2024-01-01", "2024-12-31")
            >>> df = reader.read(["000001.SZ", "000002.SZ"], "2024-01-01", "2024-12-31")
            >>> df = reader.read(None, "2024-01-01", "2024-12-31")  # 全市场
        """
        if self.lance_ds is None:
            logger.warning("[LanceDBDataReader] 数据集不存在")
            return pl.DataFrame()
        
        self._query_count += 1
        
        if fields is None:
            fields = DEFAULT_OHLCV_COLUMNS
        
        cache_key = self._make_cache_key(symbols, start_date, end_date, fields)
        
        with self._rwlock.read_lock():
            if cache_key in self._memory_cache:
                self._cache_hits += 1
                cow_df = self._memory_cache[cache_key]
                self._memory_cache.move_to_end(cache_key)
                return cow_df.read()
        
        t0 = time.perf_counter()
        
        try:
            filters = self._build_filters(symbols, start_date, end_date)
            
            scanner_kwargs = {"columns": fields}
            if filters:
                scanner_kwargs["filter"] = " AND ".join(filters)
            
            scanner = self.lance_ds.scanner(**scanner_kwargs)
            arrow_table = scanner.to_table()
            df = pl.from_arrow(arrow_table)
            
            read_time = time.perf_counter() - t0
            logger.debug(f"[LanceDBDataReader] 读取完成: {len(df)} 行, {read_time:.2f}s")
            
            if not df.is_empty():
                size_mb = self._estimate_size_mb(df)
                self._evict_lru(size_mb)
                
                with self._rwlock.write_lock():
                    cow_df = COWDataFrame(df)
                    self._memory_cache[cache_key] = cow_df
                    self._current_cache_size_mb += size_mb
            
            return df
            
        except Exception as e:
            logger.error(f"[LanceDBDataReader] 读取失败: {e}")
            return pl.DataFrame()
    
    def read_all_columns(
        self,
        symbols: Union[str, List[str], None] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        读取所有列（较慢，仅在需要全部字段时使用）
        
        Args:
            symbols: 股票代码或代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Polars DataFrame
        """
        if self.lance_ds is None:
            return pl.DataFrame()
        
        t0 = time.perf_counter()
        
        try:
            filters = self._build_filters(symbols, start_date, end_date)
            
            scanner_kwargs = {}
            if filters:
                scanner_kwargs["filter"] = " AND ".join(filters)
            
            scanner = self.lance_ds.scanner(**scanner_kwargs)
            arrow_table = scanner.to_table()
            df = pl.from_arrow(arrow_table)
            
            read_time = time.perf_counter() - t0
            logger.debug(f"[LanceDBDataReader] 全列读取完成: {len(df)} 行, {read_time:.2f}s")
            
            return df
            
        except Exception as e:
            logger.error(f"[LanceDBDataReader] 全列读取失败: {e}")
            return pl.DataFrame()
    
    def read_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        读取单个股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Polars DataFrame
        """
        return self.read(symbol, start_date, end_date)
    
    def read_batch(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        批量读取多个股票数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Polars DataFrame
        """
        if not symbols:
            return pl.DataFrame()
        
        if len(symbols) > 100:
            all_dfs = []
            for i in range(0, len(symbols), 100):
                batch = symbols[i:i+100]
                df = self.read(batch, start_date, end_date)
                if not df.is_empty():
                    all_dfs.append(df)
            if all_dfs:
                return pl.concat(all_dfs)
            return pl.DataFrame()
        return self.read(symbols, start_date, end_date)
    
    def read_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        读取全市场数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Polars DataFrame
        """
        return self.read(None, start_date, end_date)
    
    def get_latest(
        self,
        symbols: Optional[List[str]] = None,
        n: int = 1,
    ) -> pl.DataFrame:
        """
        获取最新数据
        
        Args:
            symbols: 股票代码列表，None 表示全部
            n: 返回行数
            
        Returns:
            Polars DataFrame
        """
        df = self.read(symbols)
        
        if df.is_empty():
            return pl.DataFrame()
        
        if "trade_date" in df.columns:
            df = df.sort("trade_date", descending=True).head(n)
        
        return df
    
    def list_symbols(self) -> List[str]:
        """
        列出所有股票代码
        
        Returns:
            股票代码列表
        """
        if self.lance_ds is None:
            return []
        
        try:
            scanner = self.lance_ds.scanner(columns=['stock_code'])
            arrow_table = scanner.to_table()
            codes = arrow_table.column("stock_code").to_pylist()
            return sorted(set(codes))
        except Exception as e:
            logger.error(f"[LanceDBDataReader] 获取股票列表失败: {e}")
            return []
    
    def list_dates(self) -> List[str]:
        """
        列出所有交易日期
        
        Returns:
            日期列表
        """
        if self.lance_ds is None:
            return []
        
        try:
            scanner = self.lance_ds.scanner(columns=['trade_date'])
            arrow_table = scanner.to_table()
            dates = arrow_table.column("trade_date").to_pylist()
            return sorted(set(str(d) for d in dates))
        except Exception as e:
            logger.error(f"[LanceDBDataReader] 获取日期列表失败: {e}")
            return []
    
    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取数据日期范围
        
        Returns:
            (开始日期, 结束日期)
        """
        dates = self.list_dates()
        if not dates:
            return None, None
        return dates[0], dates[-1]
    
    def preload(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        预加载数据到内存缓存
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            DataFrame
        """
        logger.info(f"[LanceDBDataReader] 预加载 {start_date} ~ {end_date}")
        
        t0 = time.perf_counter()
        df = self.read_all(start_date, end_date)
        elapsed = time.perf_counter() - t0
        
        logger.info(
            f"[LanceDBDataReader] 预加载完成: {len(df)} 行, "
            f"{elapsed:.2f}s, 缓存大小: {self._current_cache_size_mb:.1f}MB"
        )
        
        return df
    
    def preload_date_range(
        self,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
        use_multiprocess: bool = True,
    ) -> pl.DataFrame:
        """
        兼容方法：预加载指定日期范围的数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 兼容参数，忽略
            use_multiprocess: 兼容参数，忽略
            
        Returns:
            DataFrame
        """
        return self.preload(start_date, end_date)
    
    def load_bars(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        columns: Optional[List[str]] = None,
    ) -> pl.DataFrame:
        """
        兼容方法：加载行情数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            columns: 列名列表
            
        Returns:
            DataFrame
        """
        if columns and columns != ['*']:
            return self.read_batch(symbols, start_date, end_date)
        return self.read_batch(symbols, start_date, end_date)
    
    def get_cached(
        self,
        start_date: str,
        end_date: str,
    ) -> Optional[pl.DataFrame]:
        """
        兼容方法：获取缓存的数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            缓存的 DataFrame 或 None
        """
        cache_key = self._make_cache_key(None, start_date, end_date)
        with self._rwlock.read_lock():
            if cache_key in self._memory_cache:
                cow_df = self._memory_cache[cache_key]
                self._memory_cache.move_to_end(cache_key)
                return cow_df.read()
        return None
    
    def query(
        self,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
    ) -> pl.DataFrame:
        """
        兼容方法：查询数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 股票代码列表
            
        Returns:
            DataFrame
        """
        return self.read(symbols, start_date, end_date)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取读取器统计信息
        
        Returns:
            统计信息字典
        """
        with self._rwlock.read_lock():
            cache_entries = len(self._memory_cache)
            total_refs = sum(cow.get_ref_count() for cow in self._memory_cache.values())
        
        return {
            "query_count": self._query_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / max(1, self._query_count),
            "cache_size_mb": self._current_cache_size_mb,
            "cache_entries": cache_entries,
            "total_refs": total_refs,
            "total_symbols": len(self.list_symbols()),
        }
    
    def close(self):
        """关闭连接"""
        self._db = None
        self._table = None
        self._lance_ds = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


UnifiedDataReader = LanceDBDataReader

_reader_instance: Optional[LanceDBDataReader] = None
_reader_lock = threading.Lock()


def get_lancedb_reader(db_path: Optional[str] = None) -> LanceDBDataReader:
    """
    获取 LanceDBDataReader 单例（线程安全）
    
    Args:
        db_path: 数据库路径
        
    Returns:
        LanceDBDataReader 实例
    """
    global _reader_instance
    
    if _reader_instance is None:
        with _reader_lock:
            if _reader_instance is None:
                _reader_instance = LanceDBDataReader(db_path)
    
    return _reader_instance


def get_unified_reader(library_name: str = None) -> LanceDBDataReader:
    """
    兼容方法：获取 UnifiedDataReader 单例
    
    Args:
        library_name: 兼容参数，忽略
        
    Returns:
        LanceDBDataReader 实例
    """
    return get_lancedb_reader()
