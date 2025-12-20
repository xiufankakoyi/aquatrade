# database/optimized_data_query.py
"""
优化的股票数据查询类

CHANGED: 性能优化和缓存机制

主要功能：
1. get_stock_pool: 获取指定日期的股票池（核心查询，已优化）
2. get_trading_dates: 获取交易日列表
3. get_stock_history: 获取单只股票历史数据
4. preload_backtest_data: 预加载回测数据（减少 I/O）

性能优化：
- LRU 缓存机制
- 索引优化的 SQL 查询
- 数据预加载（适用于长期回测）
- 错误重试机制
"""
import os
import time
import sqlite3
from functools import lru_cache
from typing import List, Optional, Dict, Tuple, FrozenSet, Any
import pandas as pd
try:
    import duckdb  # type: ignore
except ImportError:
    duckdb = None
from database.db_utils import apply_performance_pragmas, ensure_indexes, ensure_tables
from utils.config import Config
from utils.logger import get_logger


class _DBStageTimer:
    """辅助上下文管理器，用于记录函数内部各阶段耗时"""

    def __init__(self, owner: "OptimizedStockDataQuery", func: str, stage: str):
        self.owner = owner
        self.func = func
        self.stage = stage
        self.start = 0.0
        self.metadata: Dict[str, Any] = {}

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def add_meta(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    def __exit__(self, exc_type, exc, tb):
        duration = time.perf_counter() - self.start
        if (
            self.owner._profile_verbose
            and duration >= self.owner._profile_threshold
        ):
            meta = " ".join(f"{k}={v}" for k, v in self.metadata.items())
            self.owner._logger.warning(
                f"[DB PROFILE] {self.func}.{self.stage} {duration:.3f}s {meta}".strip()
            )
        return False


class OptimizedStockDataQuery:
    def __init__(self, db_path=None, warmup: bool = True):
        self.db_path = db_path or Config.DB_PATH
        self._logger = get_logger(__name__)
        self._profile_verbose = os.getenv("DB_PROFILE_VERBOSE", "0") == "1"
        self._profile_threshold = float(os.getenv("DB_PROFILE_THRESHOLD", "0.02"))

        # 新增：后端类型，默认 sqlite，可以通过环境变量切换到 duckdb
        # Windows 下可用：set DB_BACKEND=duckdb
        backend = os.getenv("DB_BACKEND", "sqlite").lower()
        self._use_duckdb = backend == "duckdb"

        # --- DuckDB + Parquet 后端 ---
        if self._use_duckdb:
            if duckdb is None:
                raise RuntimeError("DB_BACKEND=duckdb，但未安装 duckdb，请先: pip install duckdb pyarrow")

            # parquet 目录：默认 parquet_data，可用 PARQUET_DIR 覆盖
            self.parquet_dir = os.getenv("PARQUET_DIR", "parquet_data")
            self._logger.info(f"[DB] 使用 DuckDB + Parquet 后端: dir={self.parquet_dir}")

            # DuckDB 内存库
            self.conn = duckdb.connect()

            # 注册 parquet 视图
            self._register_parquet_views()

            # SQLite 专用的 ensure_tables / PRAGMA / 索引 不再调用
        else:
            # --- 原来的 SQLite 后端 ---
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._logger.info(f"[DB] 使用 SQLite 后端: path={self.db_path}")

            # 确保数据库表存在
            ensure_tables(self.conn)

            # 统一 PRAGMA 设置，延迟 ANALYZE
            apply_performance_pragmas(self.conn, read_only=False, defer_analyze=True)
            ensure_indexes(self.conn, defer_analyze=True)

        # 预编译常用查询语句（可选优化）
        self._prepared_queries = {}

        # 缓存相关
        self._cache = {}
        self._cache_size = 200  # 增加缓存大小，减少重复查询
        self._max_trade_date_cache = None
        self._table_columns_cache: Dict[str, FrozenSet[str]] = {}

        # 预加载缓存
        self._preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
        self._preloaded_date_range: Optional[Tuple[str, str]] = None

        # 连接预热
        if warmup:
            self._warmup_connection()


    def _profile(self, func_name: str, stage: str) -> _DBStageTimer:
        return _DBStageTimer(self, func_name, stage)
    
    def _register_parquet_views(self) -> None:
        """
        DuckDB 模式下，把 parquet 文件注册成视图：
        - stock_daily
        - stock_info
        """
        import os

        # 注意 Windows 路径要换成 /，DuckDB 对反斜杠比较敏感
        daily_path = os.path.join(self.parquet_dir, "stock_daily.parquet").replace("\\", "/")
        info_path = os.path.join(self.parquet_dir, "stock_info.parquet").replace("\\", "/")

        if not os.path.exists(daily_path):
            self._logger.error(f"[DB] 找不到 {daily_path}，请确认 parquet 导出目录是否正确")
        if not os.path.exists(info_path):
            self._logger.error(f"[DB] 找不到 {info_path}，请确认 parquet 导出目录是否正确")

        # DuckDB 的 parquet_scan 会自动做列裁剪、谓词下推
        self.conn.execute(f"""
            CREATE OR REPLACE VIEW stock_daily AS
            SELECT * FROM parquet_scan('{daily_path}');
        """)
        self.conn.execute(f"""
            CREATE OR REPLACE VIEW stock_info AS
            SELECT * FROM parquet_scan('{info_path}');
        """)

        self._logger.info("[DB] DuckDB 视图注册完成: stock_daily, stock_info")
    
    def _warmup_connection(self):
        """
        预热数据库连接：执行一次简单查询，初始化连接和缓存
        """
        try:
            self.conn.execute("SELECT 1").fetchone()

            if not self._use_duckdb:
                # 只有 SQLite 才有 sqlite_master
                self.conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()

            self._logger.info("[DB] 数据库连接预热完成")
        except Exception as e:
            self._logger.warning(f"[DB] 数据库连接预热失败: {e}")

    
    def _convert_date(self, date):
        """将日期转换为字符串格式"""
        if isinstance(date, pd.Timestamp):
            return date.strftime('%Y-%m-%d')
        elif isinstance(date, str):
            return date
        else:
            return str(date)
    
    def _get_table_columns(self, table: str) -> FrozenSet[str]:
        if table in self._table_columns_cache:
            return self._table_columns_cache[table]
        try:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = frozenset(row[1] for row in rows)
            self._table_columns_cache[table] = cols
            return cols
        except Exception:
            return frozenset()
    def _query_df(self, sql: str, params=None) -> pd.DataFrame:
        """
        统一的查询 -> DataFrame：
        - sqlite: 用 pandas.read_sql
        - duckdb: 用 conn.execute(...).df()
        """
        if self._use_duckdb:
            if params is None:
                return self.conn.execute(sql).df()
            else:
                # duckdb 支持 ? 占位符
                return self.conn.execute(sql, params).df()
        else:
            return pd.read_sql(sql, self.conn, params=params)

    def _filter_existing_columns(self, columns: List[str]) -> List[str]:
        daily_cols = self._get_table_columns("stock_daily")
        info_cols = self._get_table_columns("stock_info")

        def exists(col: str) -> bool:
            if "." not in col:
                return True
            prefix, name = col.split(".", 1)
            if prefix == "s":
                return name in daily_cols
            if prefix == "i":
                return name in info_cols
            return True

        filtered = [col for col in columns if exists(col)]
        return filtered if filtered else columns

    def get_adjustment_factors(self, date: str) -> Dict[str, float]:
        """
        获取指定日期的复权因子映射。
        
        Args:
            date: 日期字符串或 Timestamp
        Returns:
            Dict[str, float]: {stock_code: adj_factor}
        """
        date_str = self._convert_date(date)
        cache_key = f"adj_factors_{date_str}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.copy() if isinstance(cached, dict) else cached

        try:
            with self._profile("get_adjustment_factors", "column_check"):
                cursor = self.conn.execute("SELECT * FROM stock_daily LIMIT 0")
                columns = [desc[0] for desc in cursor.description]
                if 'adj_factor' not in columns:
                    return {}
        except Exception as e:
            print(f"[DB] 检查 adj_factor 列失败: {e}")
            return {}

        try:
            query = """
                SELECT stock_code, adj_factor
                FROM stock_daily
                WHERE trade_date = ?
            """
            with self._profile("get_adjustment_factors", "execute_sql") as timer:
                rows = self.conn.execute(query, (date_str,)).fetchall()
                timer.add_meta(rows=len(rows))
            factors: Dict[str, float] = {}
            with self._profile("get_adjustment_factors", "build_result") as timer:
                for stock_code, factor in rows:
                    if factor is None:
                        continue
                    try:
                        factors[str(stock_code)] = float(factor)
                    except (TypeError, ValueError):
                        continue
                timer.add_meta(count=len(factors))

            self._add_to_cache(cache_key, factors)
            return factors.copy()
        except Exception as e:
            print(f"[DB] 获取复权因子失败: {e}")
            return {}
    
    def get_trading_dates(self, start_date=None, end_date=None):
        """
        CHANGED: 获取交易日列表，添加性能监控和索引优化
        """
        import time
        t0 = time.perf_counter()
        
        start_str = self._convert_date(start_date) if start_date else None
        end_str = self._convert_date(end_date) if end_date else None
        
        # 生成缓存键
        cache_key = f"trading_dates_{start_str}_{end_str}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        # CHANGED: 使用索引优化的查询
        query = "SELECT DISTINCT trade_date FROM stock_daily"
        params = []
        
        if start_date and end_date:
            query += " WHERE trade_date BETWEEN ? AND ?"
            params = [start_str, end_str]
        elif start_date:
            query += " WHERE trade_date >= ?"
            params = [start_str]
        elif end_date:
            query += " WHERE trade_date <= ?"
            params = [end_str]
            
        query += " ORDER BY trade_date"
        
        try:
            df = self._query_df(query, params)
            dates = df["trade_date"].tolist()
            elapsed = time.perf_counter() - t0
            if elapsed > 0.05:
                from utils.logger import get_logger
                logger = get_logger(__name__)
                logger.warning(f"[DB] get_trading_dates {start_str}~{end_str} -> {len(dates)} dates in {elapsed:.3f}s")
            # 缓存结果
            self._add_to_cache(cache_key, dates)
            
            return dates
        except Exception as e:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"获取交易日失败: {e}")
            return []
    
    def get_prev_trade_date(self, date: str) -> Optional[str]:
        """
        获取指定日期的前一个交易日
        
        Args:
            date: 日期字符串或 Timestamp
            
        Returns:
            前一个交易日的字符串，如果不存在则返回 None
        """
        date_str = self._convert_date(date)
        cache_key = f"prev_trade_date_{date_str}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # 获取该日期之前的所有交易日，取最后一个
            query = """
                SELECT DISTINCT trade_date 
                FROM stock_daily 
                WHERE trade_date < ?
                ORDER BY trade_date DESC 
                LIMIT 1
            """
            df = self._query_df(query, [date_str])
            
            if df.empty or df["trade_date"].empty:
                result = None
            else:
                result = str(df["trade_date"].iloc[0])
            
            self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            self._logger.error(f"获取前一个交易日失败 ({date_str}): {e}")
            return None
    
    def get_previous_trading_date(self, date: str) -> Optional[str]:
        """
        获取指定日期的前一个交易日（别名方法，兼容策略代码）
        
        Args:
            date: 日期字符串或 Timestamp
            
        Returns:
            前一个交易日的字符串，如果不存在则返回 None
        """
        return self.get_prev_trade_date(date)
    
    def get_next_trade_date(self, date: str) -> Optional[str]:
        """
        获取指定日期的下一个交易日
        
        Args:
            date: 日期字符串或 Timestamp
            
        Returns:
            下一个交易日的字符串，如果不存在则返回 None
        """
        date_str = self._convert_date(date)
        cache_key = f"next_trade_date_{date_str}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # 获取该日期之后的所有交易日，取第一个
            query = """
                SELECT DISTINCT trade_date 
                FROM stock_daily 
                WHERE trade_date > ?
                ORDER BY trade_date ASC 
                LIMIT 1
            """
            df = self._query_df(query, [date_str])
            
            if df.empty or df["trade_date"].empty:
                result = None
            else:
                result = str(df["trade_date"].iloc[0])
            
            self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            self._logger.error(f"获取下一个交易日失败 ({date_str}): {e}")
            return None
    
    def get_trading_calendar(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[str]:
        """
        获取交易日历（交易日列表）
        
        Args:
            start_date: 开始日期（可选），如果不提供则从数据库最早日期开始
            end_date: 结束日期（可选），如果不提供则到数据库最晚日期结束
            
        Returns:
            交易日列表（字符串格式，按日期升序排列）
        """
        # 如果没有指定日期范围，获取全库交易日
        if start_date is None and end_date is None:
            cache_key = "trading_calendar_all"
            if cache_key in self._cache:
                return self._cache[cache_key].copy()
            
            try:
                query = "SELECT DISTINCT trade_date FROM stock_daily ORDER BY trade_date"
                df = self._query_df(query)
                dates = df["trade_date"].tolist()
                self._add_to_cache(cache_key, dates)
                return dates.copy()
            except Exception as e:
                self._logger.error(f"获取交易日历失败: {e}")
                return []
        else:
            # 使用现有的 get_trading_dates 方法
            return self.get_trading_dates(start_date, end_date)
    
    def is_trading_day(self, date: str) -> bool:
        """
        判断指定日期是否为交易日
        
        Args:
            date: 日期字符串或 Timestamp
            
        Returns:
            True 如果是交易日，False 否则
        """
        date_str = self._convert_date(date)
        cache_key = f"is_trading_day_{date_str}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            query = "SELECT COUNT(*) as cnt FROM stock_daily WHERE trade_date = ?"
            df = self._query_df(query, [date_str])
            result = df["cnt"].iloc[0] > 0 if not df.empty else False
            self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            self._logger.error(f"判断交易日失败 ({date_str}): {e}")
            return False
            
    # --- 【【最终修复：KeyError: 'is_limit_up'】】 ---
    def get_all_daily_data_for_period(self, start_date: str, end_date: str, filters: Optional[Dict] = None) -> pd.DataFrame:
        """
        【【新】】向量化查询：一次性获取回测期间的所有股票数据
        """
        print(f"向量化加载 {start_date} 到 {end_date} 的所有数据...")
        start_str = self._convert_date(start_date)
        end_str = self._convert_date(end_date)
        
        cache_key = f"all_data_{start_str}_{end_str}"
        if cache_key in self._cache:
            print("...从缓存加载")
            return self._cache[cache_key].copy()

        # CHANGED: 只选择需要的列，避免 SELECT *（性能优化）
        # 根据实际使用情况选择列，而不是全选
        columns = [
            "s.stock_code", "s.trade_date", "s.open", "s.high", "s.low", "s.close",
            "s.prev_close", "s.volume", "s.amount", "s.total_mv", "s.float_mv",
            "s.turnover_rate", "s.turnover_free", "s.volume_ratio",
            "s.ma5", "s.ma10", "s.ma20", "s.ma60", "s.volume_ma5",
            "s.adj_factor", "s.is_limit_up", "s.is_limit_down",
            "i.is_st", "i.is_kc", "i.is_cy", "i.list_date"
        ]
        columns = self._filter_existing_columns(columns)
        column_str = ", ".join(columns)
        
        base_query = f"""
            SELECT {column_str}
            FROM stock_daily s
            LEFT JOIN stock_info i ON s.stock_code = i.stock_code
            WHERE s.trade_date BETWEEN ? AND ?
        """
        
        params = [start_str, end_str]
        
        # 默认过滤条件
        conditions = []
        if Config.EXCLUDE_ST:
            conditions.append("COALESCE(i.is_st, 0) = 0")
        if Config.EXCLUDE_KC:
            conditions.append("COALESCE(i.is_kc, 0) = 0")
        if Config.EXCLUDE_CY:
            conditions.append("COALESCE(i.is_cy, 0) = 0")
            
        conditions.extend([
            "s.total_mv IS NOT NULL",
            "s.volume > 0",
            "s.close IS NOT NULL",
        ])
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        
        try:
            result = self._query_df(query, params)
            print(f"向量化加载完成: {len(result)} 行数据")
            
            # 缓存结果
            self._add_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            print(f"向量化查询失败: {e}")
            return pd.DataFrame()
    # --- 【【修复结束】】 ---

    def get_stock_pool(self, date, filters=None, use_cache=True, columns=None):
        """
        CHANGED: ??????????????????????
        """
        import time

        logger = self._logger
        t0 = time.perf_counter()

        date_str = self._convert_date(date)
        cache_key = f"stock_pool_{date_str}_{filters}"

        if use_cache and cache_key in self._cache:
            result = self._cache[cache_key].copy()
            return result

        if columns is None:
            columns = [
                "s.stock_code", "s.trade_date", "s.open", "s.high", "s.low", "s.close",
                "s.prev_close", "s.volume", "s.amount", "s.total_mv", "s.float_mv",
                "s.turnover_rate", "s.turnover_free", "s.volume_ratio",
                "s.ma5", "s.ma10", "s.ma20", "s.volume_ma5",
                "s.adj_factor",
                "i.is_st", "i.is_kc", "i.is_cy", "i.list_date",
            ]
        columns = self._filter_existing_columns(columns)
        plain_columns = [c.split(".")[-1] for c in columns]

        preloaded_df = self.get_stock_pool_from_preloaded(date_str)
        if preloaded_df is not None:
            with self._profile("get_stock_pool", "preloaded_filter") as timer:
                filtered = self._filter_preloaded_pool(preloaded_df, filters, plain_columns)
                if filtered is not None:
                    timer.add_meta(rows=len(filtered))
                    if use_cache:
                        self._add_to_cache(cache_key, filtered)
                    return filtered

        with self._profile("get_stock_pool", "build_query"):
            column_str = ", ".join(columns)
            base_query = f"""
                SELECT {column_str}
                FROM stock_daily s
                LEFT JOIN stock_info i ON s.stock_code = i.stock_code
                WHERE s.trade_date = ?
                  AND s.total_mv IS NOT NULL
                  AND s.volume > 0
                  AND s.close IS NOT NULL
            """
            params = [date_str]

            if filters and "min_mv" in filters:
                base_query += " AND s.total_mv >= ?"
                params.append(filters["min_mv"])

            conditions = []
            if Config.EXCLUDE_ST:
                conditions.append("COALESCE(i.is_st, 0) = 0")
            if Config.EXCLUDE_KC:
                conditions.append("COALESCE(i.is_kc, 0) = 0")
            if Config.EXCLUDE_CY:
                conditions.append("COALESCE(i.is_cy, 0) = 0")

            if conditions:
                query = base_query + " AND " + " AND ".join(conditions)
            else:
                query = base_query

        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._profile("get_stock_pool", "execute_sql") as timer:
                    result = self._query_df(query, params)
                    timer.add_meta(rows=len(result))
                elapsed = time.perf_counter() - t0

                if elapsed > 0.1:
                    logger.warning(
                        f"[DB] get_stock_pool {date_str} -> {len(result)} rows in {elapsed:.3f}s"
                    )
                if elapsed > 0.5 and os.getenv("ENABLE_QUERY_PLAN") == "1":
                    try:
                        plan = self.conn.execute(f"EXPLAIN QUERY PLAN {query}", params).fetchall()
                        logger.debug(f"[DB PLAN] get_stock_pool {date_str}: {plan}")
                    except Exception as plan_err:
                        logger.debug(f"[DB PLAN] get_stock_pool {date_str} failed: {plan_err}")

                with self._profile("get_stock_pool", "post_process"):
                    if use_cache:
                        self._add_to_cache(cache_key, result)

                return result

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(
                        f"[DB] ??????{retry_delay}s ??? ({attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"[DB] ???????: {e}")
                    import traceback
                    traceback.print_exc()
                    return pd.DataFrame()

            except Exception as e:
                logger.error(f"[DB] ???????: {e}")
                import traceback
                traceback.print_exc()
                return pd.DataFrame()

        return pd.DataFrame()

    def _filter_preloaded_pool(self, df: pd.DataFrame, filters, plain_columns):
        """
        ???????????????? SQL ??
        """
        try:
            filtered = df.copy()
            filtered = filtered[
                filtered["total_mv"].notna()
                & filtered["close"].notna()
                & filtered["volume"].fillna(0).gt(0)
            ]

            if Config.EXCLUDE_ST and "is_st" in filtered.columns:
                filtered = filtered[filtered["is_st"] == 0]
            if Config.EXCLUDE_KC and "is_kc" in filtered.columns:
                filtered = filtered[filtered["is_kc"] == 0]
            if Config.EXCLUDE_CY and "is_cy" in filtered.columns:
                filtered = filtered[filtered["is_cy"] == 0]

            if filters and "min_mv" in filters and "total_mv" in filtered.columns:
                filtered = filtered[filtered["total_mv"] >= filters["min_mv"]]

            for col in plain_columns:
                if col not in filtered.columns:
                    filtered[col] = None

            return filtered[plain_columns].copy()
        except Exception as e:
            self._logger.debug(f"[DB] ???????: {e}")
            return None

    def _add_to_cache(self, key, value):
        """
        CHANGED: LRU 缓存策略
        """
        if len(self._cache) >= self._cache_size:
            # 删除最旧的项（FIFO）
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = value
    
    def get_stock_history(self, stock_code, start_date, end_date, use_cache=True, columns=None):
        """
        CHANGED: 只取所需列，避免 SELECT *
        """
        import time
        t0 = time.perf_counter()
        
        start_str = self._convert_date(start_date)
        end_str = self._convert_date(end_date)
        cache_key = f"history_{stock_code}_{start_str}_{end_str}_{columns}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        # CHANGED: 只取所需列，默认包含 adj_factor 以支持前复权
        if columns is None:
            columns = ["stock_code", "trade_date", "open", "high", "low", "close", "volume", "adj_factor"]
        column_str = ", ".join(columns)
        
        query = f"""
            SELECT {column_str}
            FROM stock_daily
            WHERE stock_code = ?
              AND trade_date BETWEEN ?
                                AND ?
            ORDER BY trade_date
        """
        try:
            result = self._query_df(query, [stock_code, start_str, end_str])
            elapsed = time.perf_counter() - t0
            if elapsed > 0.05:
                print(f"[DB] get_stock_history {stock_code} {start_str}~{end_str} -> {len(result)} rows in {elapsed:.3f}s")
            if use_cache and len(result) > 0:
                self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"获取股票历史数据失败 {stock_code}: {e}")
            return pd.DataFrame()

    def load_stock_panel(self, codes: List[str], start_date: str, end_date: str, cols: List[str]) -> pd.DataFrame:
        """
        CHANGED: 批量加载股票面板数据，只取必要列，使用分批 IN 子句
        
        Args:
            codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            cols: 需要的列名列表
        
        Returns:
            DataFrame with columns: stock_code, trade_date, and requested cols
        """
        import time
        t0 = time.perf_counter()
        
        # CHANGED: 只保留必要字段，避免多余 IO
        allowed = {
            "stock_code", "trade_date", "open", "high", "low", "close",
            "prev_close", "volume", "amount", "turnover_rate", "volume_ratio",
            "ma5", "ma10", "ma20", "volume_ma5", "total_mv", "float_mv"
        }
        cols = [c for c in cols if c in allowed]
        if "stock_code" not in cols:
            cols.insert(0, "stock_code")
        if "trade_date" not in cols:
            cols.insert(1, "trade_date")
        
        # CHANGED: 缓存键使用 frozenset 确保可哈希
        cache_key = (frozenset(codes), start_date, end_date, tuple(cols))
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        start_str = self._convert_date(start_date)
        end_str = self._convert_date(end_date)
        
        # CHANGED: SQLite 单条 IN 最多 999 个参数，分批取（使用 500 更安全）
        BATCH = 500
        frames = []
        
        # CHANGED: 对于小批量（<100），使用IN；对于大批量，考虑使用EXISTS或临时表
        # 但SQLite的IN在批量查询时通常比EXISTS更高效，所以保留IN但优化查询
        for i in range(0, len(codes), BATCH):
            chunk = codes[i:i + BATCH]
            qmarks = ",".join(["?"] * len(chunk))
            column_str = ", ".join(cols)
            
            # CHANGED: 优化查询顺序，先按日期范围过滤（使用索引），再按stock_code过滤
            sql = f"""
                SELECT {column_str}
                FROM stock_daily
                WHERE trade_date BETWEEN ? AND ?
                  AND stock_code IN ({qmarks})
                ORDER BY trade_date, stock_code
                LIMIT 1000000
            """
            params = [start_str, end_str] + chunk
            
            try:
                df_chunk = self._query_df(sql, params)
                if not df_chunk.empty:
                    frames.append(df_chunk)
            except Exception as e:
                print(f"[WARN] 批量查询失败 (批次 {i//BATCH + 1}): {e}")
                continue
        
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df.sort_values(["trade_date", "stock_code"], inplace=True)
        else:
            df = pd.DataFrame(columns=cols)
        
        elapsed = time.perf_counter() - t0
        if elapsed > 0.1:  # 只记录慢查询
            print(f"[DB] load_stock_panel {len(codes)} codes {start_date}~{end_date} -> {len(df)} rows in {elapsed:.3f}s")
        
        # CHANGED: 缓存结果
        self._add_to_cache(cache_key, df)
        return df
    
    def get_batch_stock_history(self, stock_codes, start_date, end_date, columns=None):
        """
        CHANGED: 使用 load_stock_panel 优化批量查询
        """
        if not columns:
            columns = ["stock_code", "trade_date", "open", "high", "low", "close", "volume"]
        
        return self.load_stock_panel(stock_codes, start_date, end_date, columns)
    
    def get_market_data(self, date):
        """CHANGED: 避免 SELECT *，只选择需要的列"""
        date_str = self._convert_date(date)
        # 只选择常用列，避免 SELECT * 的性能开销
        columns = [
            "s.stock_code", "s.trade_date", "s.open", "s.high", "s.low", "s.close",
            "s.prev_close", "s.volume", "s.amount", "s.total_mv", "s.float_mv",
            "s.turnover_rate", "s.volume_ratio", "s.ma5", "s.ma10", "s.ma20",
            "i.is_st", "i.is_kc", "i.is_cy"
        ]
        column_str = ", ".join(columns)
        query = f"""
            SELECT {column_str}
            FROM stock_daily s
            INNER JOIN stock_info i ON s.stock_code = i.stock_code
            WHERE s.trade_date = ?
        """
        return self._query_df(query, [date_str])
    
    def get_stock_info(self, stock_code):
        """CHANGED: 避免 SELECT *，只选择需要的列"""
        # 只选择常用列
        columns = ["stock_code", "is_st", "is_kc", "is_cy", "list_date", "name"]
        column_str = ", ".join(columns)
        query = f"SELECT {column_str} FROM stock_info WHERE stock_code = ?"
        return self._query_df(query, [stock_code])
    
    def preload_backtest_data(self, start_date: str, end_date: str) -> None:
        """
        CHANGED: 预加载回测期间的所有数据到内存
        
        性能优化：在回测开始前一次性加载所有需要的数据，避免逐日查询数据库
        适用于回测场景，可以显著减少数据库 I/O
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        """
        from utils.logger import get_logger
        
        logger = get_logger(__name__)
        start_str = self._convert_date(start_date)
        end_str = self._convert_date(end_date)

        if (
            self._preloaded_data is not None
            and self._preloaded_date_range == (start_str, end_str)
            and len(self._preloaded_data) > 0
        ):
            logger.info(f"[DB] 预加载命中缓存: {start_str} 到 {end_str}，跳过重复预加载")
            return
        
        logger.info(f"预加载回测数据: {start_str} 到 {end_str}")
        
        try:
            # 使用向量化查询一次性加载所有数据
            all_data = self.get_all_daily_data_for_period(start_str, end_str)
            
            if all_data.empty:
                logger.warning("预加载数据为空")
                self._preloaded_data = {}
                self._preloaded_date_range = (start_str, end_str)
                return
            
            # 按日期分组，存储在字典中
            self._preloaded_data = {}
            for date, group in all_data.groupby('trade_date'):
                self._preloaded_data[str(date)] = group.copy()
            
            self._preloaded_date_range = (start_str, end_str)
            logger.info(
                f"预加载完成: {len(self._preloaded_data)} 个交易日，"
                f"共 {len(all_data)} 条记录"
            )
        except Exception as e:
            logger.error(f"预加载数据失败: {e}", exc_info=True)
            self._preloaded_data = {}
            self._preloaded_date_range = (start_str, end_str)
    
    def get_stock_pool_from_preloaded(self, date: str) -> Optional[pd.DataFrame]:
        """
        CHANGED: 从预加载数据中获取股票池（如果可用）
        
        Args:
            date: 交易日期
            
        Returns:
            DataFrame 或 None（如果预加载数据不可用）
        """
        if self._preloaded_data is None:
            return None
        
        date_str = self._convert_date(date)
        return self._preloaded_data.get(date_str)
    
    def clear_preloaded_data(self) -> None:
        """清除预加载数据"""
        self._preloaded_data = None
        self._preloaded_date_range = None
    
    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        self.clear_preloaded_data()
    
    def close(self):
        """关闭数据库连接并清理资源"""
        self.clear_cache()
        self.conn.close()
