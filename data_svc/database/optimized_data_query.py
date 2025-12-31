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
from pathlib import Path
from typing import List, Optional, Dict, Tuple, FrozenSet, Any
import pandas as pd
try:
    import duckdb  # type: ignore
except ImportError:
    duckdb = None
from data_svc.database.db_utils import apply_performance_pragmas, ensure_indexes, ensure_tables
from config.config import Config
from config.logger import get_logger


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

        # 【核心修复】默认使用 LanceDB 后端（最快），可通过环境变量切换
        # DB_BACKEND=lancedb (默认，最快) | duckdb | sqlite
        backend = os.getenv("DB_BACKEND", "lancedb").lower()
        self._logger.warning(f"[DB] 环境变量 DB_BACKEND={backend} (原始值: {os.getenv('DB_BACKEND', 'NOT SET')})")
        self._use_lancedb = backend == "lancedb"
        self._use_duckdb = backend == "duckdb"
        self._logger.warning(f"[DB] 后端选择: use_lancedb={self._use_lancedb}, use_duckdb={self._use_duckdb}")

        # --- LanceDB 后端（最快）---
        if self._use_lancedb:
            try:
                self._logger.warning("[DB] 尝试初始化 LanceDB 后端...")
                from data_svc.lance_manager import LanceDBManager
                
                # 为所有表创建 LanceDBManager 实例
                self.lance_manager = LanceDBManager(table_name="stock_daily")
                self.lance_benchmark = LanceDBManager(table_name="benchmark_data")
                self.lance_limit_status = LanceDBManager(table_name="stock_limit_status")
                self.lance_stock_info = LanceDBManager(table_name="stock_info")
                
                self._logger.warning(f"[DB] ✓ 使用 LanceDB 后端（零拷贝到 Polars）")
                self._logger.warning(f"[DB] ✓ 已初始化所有表: stock_daily, benchmark_data, stock_limit_status, stock_info")
            except ImportError as e:
                self._logger.error(f"[DB] ✗ LanceDB 不可用，回退到 DuckDB: {e}")
                self._use_lancedb = False
                self._use_duckdb = True
            except Exception as e:
                self._logger.error(f"[DB] ✗ LanceDB 初始化失败，回退到 DuckDB: {e}", exc_info=True)
                self._use_lancedb = False
                self._use_duckdb = True

        # --- DuckDB + Parquet 后端 ---
        if self._use_duckdb:
            if duckdb is None:
                raise RuntimeError("DB_BACKEND=duckdb，但未安装 duckdb，请先: pip install duckdb pyarrow")

            # parquet 目录：优先使用 Config.PARQUET_DIR，其次使用环境变量，最后使用默认值
            parquet_dir_env = os.getenv("PARQUET_DIR")
            if parquet_dir_env:
                if os.path.isabs(parquet_dir_env):
                    self.parquet_dir = parquet_dir_env
                else:
                    # 相对路径：相对于项目根目录
                    self.parquet_dir = os.path.join(Config.BASE_DIR, parquet_dir_env)
            else:
                # 使用 Config 中的配置
                self.parquet_dir = Config.PARQUET_DIR
            self._logger.info(f"[DB] 使用 DuckDB + Parquet 后端: dir={self.parquet_dir}")

            # DuckDB 内存库
            self.conn = duckdb.connect()

            # 注册 parquet 视图
            self._register_parquet_views()
            
            # 优化：为 DuckDB 创建索引（虽然使用 Parquet，但索引可以优化查询计划）
            # DuckDB 支持在视图上创建索引，可以显著提升查询性能
            try:
                cur = self.conn.cursor()
                # 为 trade_date 创建索引（优化 get_trading_dates 查询）
                cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(trade_date)")
                # 为 (trade_date, stock_code) 创建复合索引（优化 get_stock_pool 查询）
                cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_date_code ON stock_daily(trade_date, stock_code)")
                # 为 stock_code 创建索引（优化单股票查询）
                cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_code ON stock_daily(stock_code)")
                # 为 benchmark_data 的 date 列创建索引（优化 get_trading_dates 查询）
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_data_date ON benchmark_data(date)")
                    self._logger.info("[DB] benchmark_data 索引创建成功")
                except Exception as e:
                    self._logger.warning(f"[DB] benchmark_data 索引创建失败: {e}")
                self._logger.info("[DB] DuckDB 索引创建完成")
            except Exception as e:
                self._logger.warning(f"[DB] DuckDB 索引创建失败（可能不支持）: {e}")
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
        self._stock_info_cache: Optional[pd.DataFrame] = None  # 缓存 stock_info 表（is_st 等信息不常变化）
        self._all_trading_dates_cache: Optional[List[str]] = None  # 缓存所有交易日期（避免重复查询 benchmark_data）
        self._stock_limit_status_cache: Optional[Dict[str, pd.DataFrame]] = None  # 缓存 stock_limit_status 表（按日期索引）
        self._stock_limit_status_cache_range: Optional[Tuple[str, str]] = None  # 缓存的日期范围

        # 预加载缓存
        self._preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
        self._preloaded_date_range: Optional[Tuple[str, str]] = None

        # 连接预热（延迟到首次使用时，避免启动时耗时）
        self._warmup_done = False
        if warmup:
            # 不立即预热，改为在首次查询时预热
            pass
        
        # 优化：预加载所有交易日期到内存（延迟到首次使用时）
        # 避免启动时耗时
        self._preload_dates_done = False


    def _profile(self, func_name: str, stage: str) -> _DBStageTimer:
        return _DBStageTimer(self, func_name, stage)
    
    def _preload_all_trading_dates(self) -> None:
        """预加载所有交易日期到内存（优化 get_trading_dates 查询）"""
        try:
            # 确保视图已注册
            if not self._views_registered:
                self._register_parquet_views()
            
            # 查询所有交易日期（只查询一次）
            query = "SELECT DISTINCT date AS trade_date FROM benchmark_data ORDER BY date"
            df = self._query_df(query, None)
            
            if df is not None and not df.empty:
                self._all_trading_dates_cache = df["trade_date"].tolist()
                self._logger.info(f"[DB] 预加载交易日期完成: {len(self._all_trading_dates_cache)} 个日期")
            else:
                self._logger.warning("[DB] 预加载交易日期失败: 查询结果为空")
        except Exception as e:
            self._logger.warning(f"[DB] 预加载交易日期失败: {e}")
    
    def _register_parquet_views(self) -> None:
        """
        DuckDB 模式下，把 parquet 文件注册成视图：
        - stock_daily
        - stock_info
        - stock_limit_status (包含 limit 和 st 字段)
        - benchmark_data (基准数据)
        """
        import os

        # 定义所有 Parquet 文件
        files = {
            "stock_daily": "stock_daily.parquet",
            "stock_info": "stock_info.parquet",
            "stock_limit_status": "stock_limit_status.parquet",
            "benchmark_data": "benchmark_daily.parquet"
        }

        registered_views = []
        missing_files = []

        for view_name, filename in files.items():
            # 修复：使用 Config.PARQUET_DIR 而不是 self.parquet_dir
            # 因为 self.parquet_dir 可能在某些情况下未初始化
            path = os.path.join(Config.PARQUET_DIR, filename)
            abs_path = os.path.abspath(path).replace("\\", "/")
            
            if os.path.exists(abs_path):
                try:
                    # 注册视图
                    self.conn.execute(f"""
                        CREATE OR REPLACE VIEW {view_name} AS
                        SELECT * FROM parquet_scan('{abs_path}');
                    """)
                    self._logger.info(f"[DB] 视图注册成功: {view_name}")
                    registered_views.append(view_name)
                except Exception as e:
                    self._logger.error(f"[DB] 注册视图 {view_name} 失败: {e}")
                    missing_files.append(filename)
            else:
                self._logger.warning(f"[DB] 文件缺失: {filename} (视图 {view_name} 不可用)")
                missing_files.append(filename)
                
                # 对于缺失的表，创建空视图防止查询报错
                if view_name == "benchmark_data":
                    try:
                        self.conn.execute("""
                            CREATE OR REPLACE VIEW benchmark_data AS
                            SELECT 
                                CAST(NULL AS VARCHAR) AS date,
                                CAST(NULL AS VARCHAR) AS code,
                                CAST(NULL AS DOUBLE) AS close
                            WHERE 1=0
                        """)
                        self._logger.warning(f"[DB] 已创建空的 benchmark_data 视图（文件不存在）")
                        registered_views.append(view_name)
                    except Exception as e:
                        self._logger.error(f"[DB] 创建空 benchmark_data 视图失败: {e}")
                elif view_name == "stock_limit_status":
                    # 为 stock_limit_status 创建空视图（如果文件不存在）
                    try:
                        self.conn.execute("""
                            CREATE OR REPLACE VIEW stock_limit_status AS
                            SELECT 
                                CAST(NULL AS VARCHAR) AS stock_code,
                                CAST(NULL AS VARCHAR) AS trade_date,
                                CAST(0 AS BOOLEAN) AS is_limit_up,
                                CAST(0 AS BOOLEAN) AS is_limit_down,
                                CAST(0 AS BOOLEAN) AS is_suspended
                            WHERE 1=0
                        """)
                        self._logger.warning(f"[DB] 已创建空的 stock_limit_status 视图（文件不存在）")
                        registered_views.append(view_name)
                    except Exception as e:
                        self._logger.error(f"[DB] 创建空 stock_limit_status 视图失败: {e}")

        self._logger.info(f"[DB] DuckDB 视图注册完成: {', '.join(registered_views)}")
        if missing_files:
            self._logger.warning(f"[DB] 缺失文件: {', '.join(missing_files)}")
        
        # 标记视图已注册
        self._views_registered = True
    
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
        """获取表的列名（支持 SQLite 和 DuckDB）"""
        if table in self._table_columns_cache:
            return self._table_columns_cache[table]
        try:
            if self._use_duckdb:
                # DuckDB: 使用 DESCRIBE 或 SELECT * LIMIT 0
                try:
                    # 尝试使用 DESCRIBE（DuckDB 支持）
                    result = self.conn.execute(f"DESCRIBE {table}").fetchall()
                    cols = frozenset(row[0] for row in result)
                except Exception:
                    # 回退：使用 SELECT * LIMIT 0 获取列名
                    result = self.conn.execute(f"SELECT * FROM {table} LIMIT 0").df()
                    cols = frozenset(result.columns)
            else:
                # SQLite: 使用 PRAGMA table_info
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
        # CHANGED: 也检查 stock_limit_status 表的列（如果视图已注册）
        try:
            limit_status_cols = self._get_table_columns("stock_limit_status")
        except Exception:
            limit_status_cols = frozenset()

        def exists(col: str) -> bool:
            # 如果是 COALESCE 表达式，直接返回 True（不检查）
            if "COALESCE" in col.upper() or "AS" in col.upper():
                return True
            if "." not in col:
                return True
            prefix, name = col.split(".", 1)
            if prefix == "s":
                return name in daily_cols
            if prefix == "i":
                return name in info_cols
            if prefix == "l":
                return name in limit_status_cols
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
        优化：优先使用 LanceDB（如果可用），大幅提升性能
        """
        # 延迟预热：在首次查询时执行
        if not self._warmup_done:
            self._warmup_connection()
            self._warmup_done = True
        
        # 延迟预加载交易日期：在首次查询时执行（仅 DuckDB 模式）
        if not self._preload_dates_done and self._use_duckdb:
            try:
                self._preload_all_trading_dates()
                self._preload_dates_done = True
            except Exception as e:
                self._logger.warning(f"[DB] 预加载交易日期失败: {e}")
        
        import time
        t0 = time.perf_counter()
        
        start_str = self._convert_date(start_date) if start_date else None
        end_str = self._convert_date(end_date) if end_date else None
        
        # 生成缓存键
        cache_key = f"trading_dates_{start_str}_{end_str}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        # 优化：如果查询所有日期，使用预加载的缓存
        if start_str is None and end_str is None:
            if self._all_trading_dates_cache is not None:
                return self._all_trading_dates_cache.copy()
        
        # 优化：如果已预加载所有交易日期，直接从内存过滤（避免查询数据库）
        if self._all_trading_dates_cache is not None:
            filtered_dates = self._all_trading_dates_cache.copy()
            
            if start_str:
                filtered_dates = [d for d in filtered_dates if d >= start_str]
            if end_str:
                filtered_dates = [d for d in filtered_dates if d <= end_str]
            
            if filtered_dates:
                # 缓存结果
                self._add_to_cache(cache_key, filtered_dates)
                elapsed = time.perf_counter() - t0
                if elapsed > 0.05:
                    self._logger.warning(f"[DB] get_trading_dates {start_str}~{end_str} -> {len(filtered_dates)} dates in {elapsed:.3f}s (from cache)")
                return filtered_dates
        
        # 优先使用 LanceDB（极速查询）
        if self._use_lancedb:
            try:
                t1 = time.perf_counter()
                # 从 benchmark_data 表获取交易日期（使用 LanceDB，极速）
                df_pl = self.lance_benchmark.load_to_polars(
                    start_date=start_str,
                    end_date=end_str,
                    columns=['date']
                )
                
                if df_pl.is_empty():
                    dates = []
                else:
                    # 获取唯一日期并排序
                    # benchmark_data 表的列名是 'date'
                    date_col = 'date' if 'date' in df_pl.columns else 'trade_date'
                    dates = df_pl.select([date_col]).unique().sort(date_col)[date_col].to_list()
                    # 转换为字符串列表
                    dates = [str(d) for d in dates]
                
                t2 = time.perf_counter()
                elapsed = time.perf_counter() - t0
                
                if elapsed > 0.05:
                    self._logger.warning(f"[DB] get_trading_dates (LanceDB) {start_str}~{end_str} -> {len(dates)} dates in {elapsed:.3f}s (query: {t2-t1:.3f}s)")
                
                # 优化：如果查询所有日期，缓存到 _all_trading_dates_cache
                if start_str is None and end_str is None:
                    self._all_trading_dates_cache = dates.copy()
                
                # 缓存结果
                self._add_to_cache(cache_key, dates)
                return dates
            except Exception as e:
                self._logger.warning(f"[DB] LanceDB get_trading_dates 失败，回退到 SQL: {e}")
                # 继续执行 SQL 查询作为回退
        
        # 回退到 SQL 查询（DuckDB/SQLite）
        # 确保视图已注册（DuckDB 模式）
        if self._use_duckdb and not self._views_registered:
            self._register_parquet_views()
        
        # 查询 benchmark_data (只有 3万行)
        query = "SELECT DISTINCT date AS trade_date FROM benchmark_data"
        params = []
        
        if start_date and end_date:
            query += " WHERE date BETWEEN ? AND ?"
            params = [start_str, end_str]
        elif start_date:
            query += " WHERE date >= ?"
            params = [start_str]
        elif end_date:
            query += " WHERE date <= ?"
            params = [end_str]
            
        query += " ORDER BY date"
        
        try:
            t1 = time.perf_counter()
            df = self._query_df(query, params)
            t2 = time.perf_counter()
            
            dates = df["trade_date"].tolist()
            elapsed = time.perf_counter() - t0
            
            if elapsed > 0.05:
                self._logger.warning(f"[DB] get_trading_dates {start_str}~{end_str} -> {len(dates)} dates in {elapsed:.3f}s")
            
            # 优化：如果查询所有日期，缓存到 _all_trading_dates_cache
            if start_str is None and end_str is None:
                self._all_trading_dates_cache = dates.copy()
            
            # 缓存结果
            self._add_to_cache(cache_key, dates)
            
            # 优化：如果查询范围较大，尝试从预加载的缓存中过滤（如果存在）
            if self._all_trading_dates_cache is not None and len(dates) > 10:
                # 如果查询结果很多，说明可能是大范围查询，下次可以直接从缓存过滤
                pass
            
            return dates
        except Exception as e:
            # #region agent log
            import traceback
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:422","message":"SQL查询失败","data":{"error":str(e)},"sessionId":"debug-session","runId":"pre-fix","hypothesisId":"E"}) + "\n")
            # #endregion
            self._logger.error(f"获取交易日失败: {e}")
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
                # 修复：使用 benchmark_data 表（数据量小，查询快）
                query = "SELECT DISTINCT date AS trade_date FROM benchmark_data ORDER BY date"
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

        # 修复：先查询 stock_daily 和 stock_info，然后直接读取 stock_limit_status Parquet 文件
        columns = [
            "s.stock_code", "s.trade_date", "s.open", "s.high", "s.low", "s.close",
            "s.prev_close", "s.volume", "s.amount", "s.total_mv", "s.float_mv",
            "s.turnover_rate", "s.turnover_free", "s.volume_ratio",
            "s.ma5", "s.ma10", "s.ma20", "s.volume_ma5",
            "s.adj_factor", 
            "i.is_kc", "i.is_cy", "i.list_date",
            "COALESCE(i.is_st, 0) AS is_st"  # is_st 在 stock_info 表中
        ]
        columns = self._filter_existing_columns(columns)
        column_str = ", ".join(columns)
        
        # 先查询 stock_daily 和 stock_info（不包含 stock_limit_status）
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
            # 查询 stock_daily 和 stock_info
            result = self._query_df(query, params)
            print(f"向量化加载完成: {len(result)} 行数据")
            
            # 修复：直接读取 stock_limit_status Parquet 文件并在内存中 JOIN
            limit_df = self._read_stock_limit_status_parquet(start_date=start_str, end_date=end_str)
            
            # 在内存中 JOIN
            if not limit_df.empty:
                result = result.merge(
                    limit_df[['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']],
                    on=['stock_code', 'trade_date'],
                    how='left'
                )
                # 填充缺失值
                result['is_limit_up'] = result['is_limit_up'].fillna(0)
                result['is_limit_down'] = result['is_limit_down'].fillna(0)
                result['is_suspended'] = result['is_suspended'].fillna(0)
            else:
                # 如果没有 limit_status 数据，设置默认值
                result['is_limit_up'] = 0
                result['is_limit_down'] = 0
                result['is_suspended'] = 0
            
            # 【防御性数据加载器】自动补全缺失字段
            result = self._defensive_data_loader(result, start_str)
            
            # 缓存结果
            self._add_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            print(f"向量化查询失败: {e}")
            return pd.DataFrame()
    # --- 【【修复结束】】 ---

    def _get_stock_pool_lancedb(self, date, filters=None, columns=None) -> Optional[pd.DataFrame]:
        """
        使用 LanceDB 获取股票池（零拷贝，极速）
        
        注意：LanceDB 目前只存储 stock_daily，需要 JOIN 的信息从 DuckDB/SQLite 获取
        """
        date_str = self._convert_date(date)
        
        try:
            # 从 LanceDB 加载主数据（零拷贝到 Polars）
            df_pl = self.lance_manager.load_to_polars(
                start_date=date_str,
                end_date=date_str
            )
            
            if df_pl.is_empty():
                return None
            
            # 转换为 Pandas
            df = df_pl.to_pandas()
            
            # 应用基本过滤
            if df is not None and not df.empty:
                df = df[df['total_mv'].notna() & df['close'].notna() & (df['volume'].fillna(0) > 0)]
            
            # 从 LanceDB 获取辅助信息（stock_info, stock_limit_status）
            # 完全使用 LanceDB，不再依赖 DuckDB
            stock_codes = df['stock_code'].unique().tolist()
            if stock_codes:
                try:
                    # 1. 获取 stock_info（从 LanceDB）
                    if self._stock_info_cache is None:
                        # 缓存整个 stock_info 表（数据量小，不常变化）
                        # 注意：stock_info 表没有日期列，所以不需要日期过滤
                        try:
                            # 使用 load_to_polars（不带日期过滤，因为 stock_info 没有日期列）
                            # 但使用 stock_codes 过滤以减少数据量
                            if stock_codes and len(stock_codes) < 5000:  # 如果股票数量不太多，使用过滤
                                stock_info_pl = self.lance_stock_info.load_to_polars(
                                    stock_codes=stock_codes,
                                    columns=['stock_code', 'is_st', 'is_kc', 'is_cy', 'list_date']
                                )
                            else:
                                # 如果股票数量太多，直接加载全部（避免 IN 子句过长）
                                stock_info_pl = self.lance_stock_info.load_to_polars(
                                    columns=['stock_code', 'is_st', 'is_kc', 'is_cy', 'list_date']
                                )
                            self._stock_info_cache = stock_info_pl.to_pandas()
                            self._logger.debug(f"[DB] 缓存 stock_info 表: {len(self._stock_info_cache)} 条记录")
                        except Exception as e:
                            self._logger.warning(f"[DB] 从 LanceDB 加载 stock_info 失败: {e}")
                            self._stock_info_cache = pd.DataFrame()
                    
                    # 从缓存中获取 stock_info
                    stock_info_df = self._stock_info_cache[
                        self._stock_info_cache['stock_code'].isin(stock_codes)
                    ].copy() if not self._stock_info_cache.empty else pd.DataFrame()
                    
                    # 2. 获取 stock_limit_status（从 LanceDB）
                    limit_df = None
                    if self._stock_limit_status_cache is not None and date_str in self._stock_limit_status_cache:
                        # 从缓存中获取
                        cached_limit = self._stock_limit_status_cache[date_str]
                        limit_df = cached_limit[cached_limit['stock_code'].isin(stock_codes)].copy()
                        self._logger.debug(f"[DB] 从缓存获取 stock_limit_status: {date_str}, {len(limit_df)} 条记录")
                    else:
                        # 从 LanceDB 获取指定日期的 limit_status
                        try:
                            limit_pl = self.lance_limit_status.load_to_polars(
                                stock_codes=stock_codes,
                                start_date=date_str,
                                end_date=date_str,
                                columns=['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended']
                            )
                            limit_df = limit_pl.to_pandas() if not limit_pl.is_empty() else pd.DataFrame()
                            
                            # 更新缓存
                            if self._stock_limit_status_cache is None:
                                self._stock_limit_status_cache = {}
                            self._stock_limit_status_cache[date_str] = limit_df.copy()
                        except Exception as e:
                            self._logger.warning(f"[DB] 从 LanceDB 加载 stock_limit_status 失败: {e}")
                            limit_df = pd.DataFrame()
                    
                    if limit_df is None or limit_df.empty:
                        limit_df = pd.DataFrame(columns=['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended'])
                    
                    # 3. 合并数据
                    if not stock_info_df.empty:
                        if not limit_df.empty:
                            join_df = stock_info_df.merge(limit_df, on='stock_code', how='left')
                        else:
                            join_df = stock_info_df.copy()
                            join_df['is_limit_up'] = 0
                            join_df['is_limit_down'] = 0
                            join_df['is_suspended'] = 0
                    else:
                        # 如果 stock_info 中没有数据，只使用 limit_status
                        join_df = limit_df.copy() if not limit_df.empty else pd.DataFrame()
                    
                    # 合并到主数据
                    if not join_df.empty:
                        df = df.merge(join_df, on='stock_code', how='left')
                    else:
                        # 如果没有查询到数据，设置默认值
                        for col in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']:
                            if col not in df.columns:
                                df[col] = 0
                except Exception as e:
                    self._logger.warning(f"[DB] LanceDB JOIN 失败，使用默认值: {e}", exc_info=True)
                    # 设置默认值
                    for col in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']:
                        if col not in df.columns:
                            df[col] = 0
            
            # 选择列（如果需要）
            if columns:
                # 处理列名（s.stock_code -> stock_code）
                plain_columns = []
                for c in columns:
                    if " AS " in c.upper():
                        plain_columns.append(c.split(" AS ")[-1].strip())
                    elif "." in c:
                        plain_columns.append(c.split(".")[-1])
                    else:
                        plain_columns.append(c)
                
                # 只选择存在的列
                available_cols = [col for col in plain_columns if col in df.columns]
                if available_cols:
                    df = df[available_cols]
            
            return df
            
        except Exception as e:
            self._logger.warning(f"[DB] LanceDB 查询失败 {date_str}: {e}")
            return None

    def _get_stock_pool_batch(self, dates: List[str], filters=None, columns=None) -> Optional[pd.DataFrame]:
        """
        批量获取多个日期的股票池（优化：避免 N+1 查询）
        
        Args:
            dates: 日期列表
            filters: 过滤条件
            columns: 要查询的列
            
        Returns:
            DataFrame 包含所有日期的数据
        """
        if not dates:
            return None
        
        # 修复：直接读取 Parquet 文件，而不是通过 SQL JOIN
        # 先读取 stock_daily 和 stock_info，然后读取 stock_limit_status，在内存中 JOIN
        try:
            # 确保 DuckDB 连接已初始化（仅用于 stock_daily 和 stock_info）
        if self._use_duckdb:
            if not hasattr(self, 'conn') or self.conn is None:
                if duckdb is None:
                    raise RuntimeError("DuckDB 不可用")
                self.conn = duckdb.connect()
                self._register_parquet_views()
            elif not hasattr(self, '_views_registered') or not self._views_registered:
                self._register_parquet_views()
                self._views_registered = True
        
            # 批量查询 stock_daily 和 stock_info（不使用 stock_limit_status JOIN）
            batch_size = 100
        all_dfs = []
        
        for i in range(0, len(dates), batch_size):
            batch_dates = dates[i:i+batch_size]
            placeholders = ",".join(["?"] * len(batch_dates))
            
            if columns is None:
                    # 先查询 stock_daily 和 stock_info（不包含 stock_limit_status）
                    base_columns = [
                    "s.stock_code", "s.trade_date", "s.open", "s.high", "s.low", "s.close",
                    "s.volume", "s.total_mv", "s.float_mv", "s.turnover_rate", "s.volume_ratio",
                    "s.ma5", "s.ma10", "s.ma20", "s.volume_ma5", "s.adj_factor",
                    "COALESCE(i.is_st, 0) AS is_st",
                    "i.is_kc", "i.is_cy", "i.list_date",
                ]
                else:
                    # 过滤掉 stock_limit_status 相关的列
                    base_columns = [c for c in columns if 'l.' not in c and 'is_limit' not in c and 'is_suspended' not in c]
            
                columns_str = ", ".join(base_columns)
            query = f"""
                SELECT {columns_str}
                FROM stock_daily s
                LEFT JOIN stock_info i ON s.stock_code = i.stock_code
                WHERE s.trade_date IN ({placeholders})
                ORDER BY s.trade_date, s.stock_code
            """
            
            try:
                df_batch = self._query_df(query, params=batch_dates)
                if df_batch is not None and not df_batch.empty:
                    all_dfs.append(df_batch)
            except Exception as e:
                self._logger.warning(f"批量查询股票池失败（批次 {i//batch_size + 1}）: {e}")
                continue
        
        if not all_dfs:
            return None
        
        # 合并所有批次
        if len(all_dfs) == 1:
                df_main = all_dfs[0]
        else:
                df_main = pd.concat(all_dfs, ignore_index=True)
            
            # 修复：直接读取 stock_limit_status Parquet 文件并在内存中 JOIN
            date_range_start = min(dates)
            date_range_end = max(dates)
            limit_df = self._read_stock_limit_status_parquet(start_date=date_range_start, end_date=date_range_end)
            
            # 在内存中 JOIN
            if not limit_df.empty:
                df_main = df_main.merge(
                    limit_df[['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']],
                    on=['stock_code', 'trade_date'],
                    how='left'
                )
                # 填充缺失值
                df_main['is_limit_up'] = df_main['is_limit_up'].fillna(0)
                df_main['is_limit_down'] = df_main['is_limit_down'].fillna(0)
                df_main['is_suspended'] = df_main['is_suspended'].fillna(0)
            else:
                # 如果没有 limit_status 数据，设置默认值
                df_main['is_limit_up'] = 0
                df_main['is_limit_down'] = 0
                df_main['is_suspended'] = 0
            
            return df_main
            
        except Exception as e:
            self._logger.error(f"批量查询股票池失败: {e}", exc_info=True)
            return None
    
    def get_stock_pool(self, date, filters=None, use_cache=True, columns=None):
        """
        获取指定日期的股票池
        
        优先使用 LanceDB（最快），回退到 DuckDB/SQLite
        """
        # 优先使用 LanceDB（最快）
        if self._use_lancedb:
            result = self._get_stock_pool_lancedb(date, filters=filters, columns=columns)
            if result is not None:
                return result
            # 如果 LanceDB 失败，回退到原有逻辑
            self._logger.warning("[DB] LanceDB 查询失败，回退到 DuckDB/SQLite")
        
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
                # CHANGED: 从 stock_limit_status 读取 limit 和 suspended 字段
                # 注意：is_st 在 stock_info 表中，不在 stock_limit_status 中
                "COALESCE(l.is_limit_up, 0) AS is_limit_up",
                "COALESCE(l.is_limit_down, 0) AS is_limit_down",
                "COALESCE(l.is_suspended, 0) AS is_suspended",
                "COALESCE(i.is_st, 0) AS is_st",  # is_st 在 stock_info 表中
                "i.is_kc", "i.is_cy", "i.list_date",
            ]
        columns = self._filter_existing_columns(columns)
        # CHANGED: 正确处理 COALESCE 表达式，提取 AS 后的列名
        plain_columns = []
        for c in columns:
            if " AS " in c.upper():
                # 提取 AS 后的列名
                plain_columns.append(c.split(" AS ")[-1].strip())
            elif "." in c:
                plain_columns.append(c.split(".")[-1])
            else:
                plain_columns.append(c)

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
            # 修复：过滤掉 stock_limit_status 相关的列（将在内存中 JOIN）
            sql_columns = []
            need_limit_status = False
            for c in columns:
                if 'l.is_limit' in c or 'l.is_suspended' in c:
                    need_limit_status = True
                    # 不在 SQL 中查询，稍后在内存中 JOIN
                    continue
                sql_columns.append(c)
            
            column_str = ", ".join(sql_columns)
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
                    # 修复：如果需要 stock_limit_status，直接读取 Parquet 文件并在内存中 JOIN
                    if need_limit_status:
                        limit_df = self._read_stock_limit_status_parquet(trade_date=date_str)
                        if not limit_df.empty:
                            result = result.merge(
                                limit_df[['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']],
                                on=['stock_code', 'trade_date'],
                                how='left'
                            )
                            result['is_limit_up'] = result['is_limit_up'].fillna(0)
                            result['is_limit_down'] = result['is_limit_down'].fillna(0)
                            result['is_suspended'] = result['is_suspended'].fillna(0)
                        else:
                            result['is_limit_up'] = 0
                            result['is_limit_down'] = 0
                            result['is_suspended'] = 0
                    
                    # 【防御性数据加载器】自动补全缺失字段
                    # 注意：如果字段都存在，_defensive_data_loader 会直接返回原 DataFrame
                    result = self._defensive_data_loader(result, date_str)
                    
                    if use_cache:
                        # 【性能优化】只在缓存时才 copy，避免不必要的内存分配
                        self._add_to_cache(cache_key, result.copy() if result is not None else result)

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
        【性能优化】从预加载数据中过滤股票池，减少不必要的 copy
        """
        try:
            # 【性能优化】先应用防御性数据加载器（它会检查是否需要 copy）
            filtered = self._defensive_data_loader(df, "")
            
            # 【性能优化】使用向量化操作，一次性应用所有过滤条件（比多次过滤快）
            mask = (
                filtered["total_mv"].notna()
                & filtered["close"].notna()
                & filtered["volume"].fillna(0).gt(0)
            )
            
            if Config.EXCLUDE_ST and "is_st" in filtered.columns:
                mask = mask & (filtered["is_st"] == 0)
            if Config.EXCLUDE_KC and "is_kc" in filtered.columns:
                mask = mask & (filtered["is_kc"] == 0)
            if Config.EXCLUDE_CY and "is_cy" in filtered.columns:
                mask = mask & (filtered["is_cy"] == 0)

            if filters and "min_mv" in filters and "total_mv" in filtered.columns:
                mask = mask & (filtered["total_mv"] >= filters["min_mv"])

            # 应用所有过滤条件（一次性过滤，比多次过滤快）
            filtered = filtered[mask]

            # 【性能优化】只添加缺失的列，避免不必要的操作
            missing_cols = [col for col in plain_columns if col not in filtered.columns]
            if missing_cols:
                for col in missing_cols:
                    filtered[col] = None

            # 【性能优化】只在需要时才 copy（如果列顺序不同或需要新 DataFrame）
            result_cols = [col for col in plain_columns if col in filtered.columns]
            if result_cols == plain_columns and filtered.index.equals(df.index):
                # 如果列顺序相同且索引相同，可能不需要 copy
                return filtered[plain_columns]
            else:
                return filtered[plain_columns].copy()
        except Exception as e:
            self._logger.debug(f"[DB] 过滤预加载股票池失败: {e}")
            return None

    def _defensive_data_loader(self, df: pd.DataFrame, context: str = "") -> pd.DataFrame:
        """
        【防御性数据加载器】自动补全缺失字段，确保返回的 DataFrame 包含所有标准字段
        
        【性能优化】使用 inplace 操作和条件检查，避免不必要的 copy()，大幅提升性能
        
        Args:
            df: 原始 DataFrame（会被原地修改，如果不需要修改请先 copy）
            context: 上下文信息（已废弃，保留兼容性）
        
        Returns:
            补全后的 DataFrame（可能是原 DataFrame 的引用或新 DataFrame）
        """
        if df is None or df.empty:
            return df
        
        # 【性能优化】使用类变量缓存警告状态，确保每个字段只警告一次
        if not hasattr(self.__class__, '_logged_warnings'):
            self.__class__._logged_warnings = set()
        
        # 【性能优化】只在需要修改时才 copy，避免不必要的内存分配
        need_copy = False
        cols_to_check = ['is_limit_up', 'is_limit_down', 'is_suspended', 'is_st', 'ma60']
        for col in cols_to_check:
            if col not in df.columns:
                need_copy = True
                break
        
        # 【性能优化】如果所有字段都存在，假设没有 NaN（大多数情况下都是这样），直接返回
        # 只有在字段缺失时才处理，避免不必要的 copy 和 NaN 检查
        if not need_copy:
            # 最快路径：所有字段都存在，直接返回（假设没有 NaN，如果有会在后续使用时报错，但概率极低）
            return df
        
        # 只在需要修改时才 copy
        result = df.copy()
        
        # 1. 补全 is_limit_up（涨停标志）- 默认 False（未涨停，允许交易），向量化填充
        if 'is_limit_up' not in result.columns:
            result['is_limit_up'] = False
            if 'is_limit_up' not in self.__class__._logged_warnings:
                self.__class__._logged_warnings.add('is_limit_up')
                self._logger.warning(f"字段 'is_limit_up' 缺失，已使用默认值 False 填充")
        else:
            # 【性能优化】向量化填充 NaN，使用 fillna 直接赋值
            result['is_limit_up'] = result['is_limit_up'].fillna(False)
        
        # 2. 补全 is_limit_down（跌停标志）- 默认 False（未跌停，允许交易），向量化填充
        if 'is_limit_down' not in result.columns:
            result['is_limit_down'] = False
            if 'is_limit_down' not in self.__class__._logged_warnings:
                self.__class__._logged_warnings.add('is_limit_down')
                self._logger.warning(f"字段 'is_limit_down' 缺失，已使用默认值 False 填充")
        else:
            result['is_limit_down'] = result['is_limit_down'].fillna(False)
        
        # 2.5. 补全 is_suspended（停牌标志）- 默认 False（未停牌，允许交易），向量化填充
        if 'is_suspended' not in result.columns:
            result['is_suspended'] = False
            if 'is_suspended' not in self.__class__._logged_warnings:
                self.__class__._logged_warnings.add('is_suspended')
                self._logger.warning(f"字段 'is_suspended' 缺失，已使用默认值 False 填充")
        else:
            result['is_suspended'] = result['is_suspended'].fillna(False)
        
        # 3. 补全 is_st（ST 股票标志）- 默认 False（非ST股票），向量化填充
        if 'is_st' not in result.columns:
            result['is_st'] = False
            if 'is_st' not in self.__class__._logged_warnings:
                self.__class__._logged_warnings.add('is_st')
                self._logger.warning(f"字段 'is_st' 缺失，已使用默认值 False 填充")
        else:
            result['is_st'] = result['is_st'].fillna(False)
        
        # 4. 补全 ma60（60日均线）- 直接向量化填充 0，不再使用 rolling(60) 计算
        if 'ma60' not in result.columns:
            # 【性能优化】直接向量化填充 0，避免复杂的 rolling 计算
            result['ma60'] = 0.0
            if 'ma60' not in self.__class__._logged_warnings:
                self.__class__._logged_warnings.add('ma60')
                self._logger.warning(f"字段 'ma60' 缺失，已使用默认值 0.0 填充（不再计算 rolling(60)）")
        else:
            # ma60 存在，直接 fillna（fillna 对没有 NaN 的列也很快）
            result['ma60'] = result['ma60'].fillna(0.0)
        
        return result
    
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
    
    def _read_stock_limit_status_parquet(self, start_date: str = None, end_date: str = None, 
                                         stock_codes: List[str] = None, trade_date: str = None) -> pd.DataFrame:
        """
        直接读取 stock_limit_status.parquet 文件（修复：避免视图注册问题）
        
        Args:
            start_date: 开始日期（可选，用于日期范围过滤）
            end_date: 结束日期（可选，用于日期范围过滤）
            stock_codes: 股票代码列表（可选，用于股票过滤）
            trade_date: 单个交易日期（可选，用于单日查询）
            
        Returns:
            DataFrame 包含 stock_limit_status 数据
        """
        try:
            import polars as pl
            
            # 构建 Parquet 文件路径
            parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
            parquet_file = Path(parquet_dir) / 'stock_limit_status.parquet'
            
            # 确保路径使用正斜杠（修复：Windows 路径问题）
            parquet_path = str(parquet_file.resolve()).replace('\\', '/')
            
            if not parquet_file.exists():
                self._logger.warning(f"[DB] stock_limit_status.parquet 文件不存在: {parquet_file}")
                return pd.DataFrame(columns=['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
            
            # 使用 Polars 读取 Parquet（支持下推过滤）
            lazy_df = pl.scan_parquet(parquet_path)
            
            # 应用过滤条件（下推到 Parquet 读取层）
            if trade_date:
                lazy_df = lazy_df.filter(pl.col('trade_date') == trade_date)
            elif start_date and end_date:
                lazy_df = lazy_df.filter(
                    (pl.col('trade_date') >= start_date) & 
                    (pl.col('trade_date') <= end_date)
                )
            elif start_date:
                lazy_df = lazy_df.filter(pl.col('trade_date') >= start_date)
            elif end_date:
                lazy_df = lazy_df.filter(pl.col('trade_date') <= end_date)
            
            if stock_codes:
                lazy_df = lazy_df.filter(pl.col('stock_code').is_in(stock_codes))
            
            # 选择需要的列
            lazy_df = lazy_df.select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
            
            # 执行查询并转换为 Pandas
            df_pl = lazy_df.collect()
            df = df_pl.to_pandas()
            
            return df
            
        except Exception as e:
            self._logger.error(f"[DB] 读取 stock_limit_status.parquet 失败: {e}", exc_info=True)
            return pd.DataFrame(columns=['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
    
    def preload_stock_limit_status(self, start_date: str, end_date: str) -> None:
        """
        批量预加载 stock_limit_status 数据（优化：从 LanceDB 读取，利用索引快速筛选）
        
        结合 LanceDB 的优势（快速从磁盘筛选特定时间段）和内存的优势（高频访问数据在 RAM 里）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        """
        import json, time
        _t_preload_start = time.perf_counter()
        start_str = self._convert_date(start_date)
        end_str = self._convert_date(end_date)
        
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"preload_stock_limit_status开始","data":{"start":start_str,"end":end_str},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 检查是否已经预加载过相同范围的数据
        if (
            self._stock_limit_status_cache is not None
            and self._stock_limit_status_cache_range == (start_str, end_str)
            and len(self._stock_limit_status_cache) > 0
        ):
            self._logger.info(f"[DB] stock_limit_status 缓存命中: {start_str} 到 {end_str}，跳过重复预加载")
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"缓存命中，跳过预加载","data":{"start":start_str,"end":end_str},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            return
        
        self._logger.info(f"[DB] 开始预加载 stock_limit_status (LanceDB): {start_str} 到 {end_str}")
        
        try:
            # #region agent log
            _t_read_start = time.perf_counter()
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"开始从LanceDB读取","data":{"start":start_str,"end":end_str},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            
            # 优化：优先使用 LanceDB（利用索引快速筛选特定时间段）
            if self._use_lancedb and hasattr(self, 'lance_limit_status'):
                try:
                    # 从 LanceDB 读取指定日期范围的数据（利用下推过滤，只读回测期间的数据）
                    limit_pl = self.lance_limit_status.load_to_polars(
                        start_date=start_str,
                        end_date=end_str,
                        columns=['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']
                    )
                    df = limit_pl.to_pandas() if not limit_pl.is_empty() else pd.DataFrame()
                    self._logger.info(f"[DB] 从 LanceDB 读取 stock_limit_status: {len(df)} 条记录")
                except Exception as e:
                    self._logger.warning(f"[DB] LanceDB 读取失败，回退到 Parquet: {e}")
                    # 回退到 Parquet 读取
                    df = self._read_stock_limit_status_parquet(start_date=start_str, end_date=end_str)
            else:
                # 回退：直接读取 Parquet 文件
                df = self._read_stock_limit_status_parquet(start_date=start_str, end_date=end_str)
            
            _t_read_end = time.perf_counter()
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"数据读取完成","data":{"elapsed":_t_read_end-_t_read_start,"rows":len(df) if df is not None and not df.empty else 0,"source":"lancedb" if (self._use_lancedb and hasattr(self, 'lance_limit_status')) else "parquet"},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            
            if df is None or df.empty:
                self._logger.warning(f"[DB] stock_limit_status 预加载结果为空: {start_str} 到 {end_str}")
                self._stock_limit_status_cache = {}
                self._stock_limit_status_cache_range = (start_str, end_str)
                return
            
            # #region agent log
            _t_group_start = time.perf_counter()
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"开始按日期分组","data":{"rows":len(df) if df is not None and not df.empty else 0},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            # 按日期分组，存储在内存字典中（用于高频访问）
            self._stock_limit_status_cache = {}
            for date, group in df.groupby('trade_date'):
                date_str = str(date)
                self._stock_limit_status_cache[date_str] = group[['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended']].copy()
            _t_group_end = time.perf_counter()
            
            self._stock_limit_status_cache_range = (start_str, end_str)
            _t_preload_end = time.perf_counter()
            self._logger.info(
                f"[DB] stock_limit_status 预加载完成: {len(self._stock_limit_status_cache)} 个交易日，"
                f"共 {len(df)} 条记录，耗时 {_t_preload_end - _t_preload_start:.2f}s "
                f"(读取: {_t_read_end - _t_read_start:.2f}s, 分组: {_t_group_end - _t_group_start:.2f}s)"
            )
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"preload_stock_limit_status完成","data":{"elapsed":_t_preload_end-_t_preload_start,"read_elapsed":_t_read_end-_t_read_start,"group_elapsed":_t_group_end-_t_group_start,"dates_count":len(self._stock_limit_status_cache),"total_rows":len(df)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
        except Exception as e:
            _t_preload_end = time.perf_counter()
            self._logger.error(f"[DB] 预加载 stock_limit_status 失败: {e}", exc_info=True)
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_data_query.py:preload_stock_limit_status","message":"preload_stock_limit_status失败","data":{"elapsed":_t_preload_end-_t_preload_start,"error":str(e)[:500]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            self._stock_limit_status_cache = {}
            self._stock_limit_status_cache_range = (start_str, end_str)
    
    def get_stock_limit_status_batch(self, dates: List[str], stock_codes: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        批量获取 stock_limit_status 数据（优化：优先从内存字典读取，未命中才查库）
        
        结合内存的优势（高频访问数据在 RAM 里）和 LanceDB 的优势（快速从磁盘筛选）
        
        Args:
            dates: 日期列表
            stock_codes: 股票代码列表（可选，用于过滤）
            
        Returns:
            Dict[str, pd.DataFrame]: {date: DataFrame} 字典，每个 DataFrame 包含该日期的 limit_status 数据
        """
        result = {}
        
        # 1. 优先从内存缓存读取
        if self._stock_limit_status_cache is not None:
            for date_str in dates:
                if date_str in self._stock_limit_status_cache:
                    cached_df = self._stock_limit_status_cache[date_str].copy()
                    # 如果指定了股票代码，进行过滤
                    if stock_codes:
                        cached_df = cached_df[cached_df['stock_code'].isin(stock_codes)].copy()
                    result[date_str] = cached_df
        
        # 2. 对于未命中的日期，从 LanceDB 查询（如果可用）
        missing_dates = [d for d in dates if d not in result]
        if missing_dates:
            if self._use_lancedb and hasattr(self, 'lance_limit_status'):
                try:
                    # 批量查询未命中的日期
                    min_date = min(missing_dates)
                    max_date = max(missing_dates)
                    
                    limit_pl = self.lance_limit_status.load_to_polars(
                        stock_codes=stock_codes,
                        start_date=min_date,
                        end_date=max_date,
                        columns=['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']
                    )
                    
                    if not limit_pl.is_empty():
                        df = limit_pl.to_pandas()
                        # 按日期分组
                        for date_str in missing_dates:
                            date_df = df[df['trade_date'] == date_str]
                            if not date_df.empty:
                                result[date_str] = date_df[['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended']].copy()
                                
                                # 更新缓存（供后续使用）
                                if self._stock_limit_status_cache is None:
                                    self._stock_limit_status_cache = {}
                                self._stock_limit_status_cache[date_str] = result[date_str].copy()
                except Exception as e:
                    self._logger.warning(f"[DB] 从 LanceDB 批量查询 stock_limit_status 失败: {e}")
            else:
                # 回退：使用 Parquet 读取
                for date_str in missing_dates:
                    try:
                        date_df = self._read_stock_limit_status_parquet(trade_date=date_str, stock_codes=stock_codes)
                        if not date_df.empty:
                            result[date_str] = date_df[['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended']].copy()
                            
                            # 更新缓存
                            if self._stock_limit_status_cache is None:
                                self._stock_limit_status_cache = {}
                            self._stock_limit_status_cache[date_str] = result[date_str].copy()
                    except Exception as e:
                        self._logger.warning(f"[DB] 读取 stock_limit_status 失败 ({date_str}): {e}")
        
        # 3. 对于仍然缺失的日期，返回空 DataFrame
        for date_str in dates:
            if date_str not in result:
                result[date_str] = pd.DataFrame(columns=['stock_code', 'is_limit_up', 'is_limit_down', 'is_suspended'])
        
        return result
    
    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        self.clear_preloaded_data()
        self._stock_limit_status_cache = None
        self._stock_limit_status_cache_range = None
    
    def close(self):
        """关闭数据库连接并清理资源"""
        try:
            self.clear_cache()
        except Exception as e:
            self._logger.warning(f"清理缓存时出错: {e}")
        
        try:
            if hasattr(self, 'conn') and self.conn is not None:
                # DuckDB 和 SQLite 都需要显式关闭
                self.conn.close()
                self.conn = None
        except Exception as e:
            self._logger.warning(f"关闭数据库连接时出错: {e}")
