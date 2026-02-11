# database/db_utils.py
"""
数据库性能优化工具函数

CHANGED: 统一 PRAGMA 设置和索引创建，提升数据库查询性能

主要功能：
1. apply_performance_pragmas: 设置 SQLite 性能优化参数
2. ensure_indexes: 确保关键索引存在
3. ensure_tables: 确保数据库表结构正确
4. create_readonly_connection: 创建只读连接（多线程安全）
"""
import sqlite3
import time
from typing import Optional


def apply_performance_pragmas(conn: sqlite3.Connection, read_only: bool = False, defer_analyze: bool = True) -> None:
    """
    统一设置 SQLite 性能优化 PRAGMA
    
    Args:
        conn: SQLite 连接对象
        read_only: 是否为只读连接
        defer_analyze: 是否延迟执行 ANALYZE（在后台线程执行，避免阻塞启动）
    """
    cur = conn.cursor()
    
    # CHANGED: 统一性能优化 PRAGMA
    pragmas = [
        ("PRAGMA journal_mode=WAL;", None),
        ("PRAGMA synchronous=NORMAL;", None),
        ("PRAGMA temp_store=MEMORY;", None),
        ("PRAGMA mmap_size=30000000000;", None),  # 约 30GB，可根据机器调整到 1-4GB
        ("PRAGMA cache_size=-200000;", None),     # 约 200MB 页面缓存
        ("PRAGMA busy_timeout=8000;", None),
        ("PRAGMA foreign_keys=ON;", None),
    ]
    
    for pragma, _ in pragmas:
        try:
            cur.execute(pragma)
        except sqlite3.Error as e:
            print(f"[WARN] 设置 PRAGMA 失败: {pragma} - {e}")
    
    # CHANGED: 延迟执行 ANALYZE，避免阻塞启动
    if not read_only and not defer_analyze:
        try:
            cur.execute("ANALYZE;")
        except sqlite3.Error:
            pass  # ANALYZE 可能失败，忽略
    
    conn.commit()
    
    # 【关键修复】注释掉后台 ANALYZE 执行
    # 原因：对于1500万行的数据表，ANALYZE 需要扫描大量数据块，耗时30秒+
    # ANALYZE 操作在数据写入后做一次就够了，不应该在每次读数据前都做
    # 如果需要更新统计信息，应该手动执行，而不是自动执行
    # if not read_only and defer_analyze:
    #     import threading
    #     def _analyze_background():
    #         try:
    #             time.sleep(0.5)  # 延迟 0.5 秒，让主流程先完成
    #             cur.execute("ANALYZE;")
    #             conn.commit()
    #             print("[DB] 后台 ANALYZE 完成")
    #         except Exception as e:
    #             print(f"[WARN] 后台 ANALYZE 失败: {e}")
    #     
    #     threading.Thread(target=_analyze_background, daemon=True).start()


def ensure_indexes(conn: sqlite3.Connection, defer_analyze: bool = True) -> None:
    """
    确保必要的索引存在
    
    CHANGED: 创建覆盖典型查询的索引，优化查询性能
    
    索引策略说明：
    1. idx_stock_daily_code_date: 覆盖按股票代码和日期的精确查询
    2. idx_stock_daily_date_code: 覆盖按日期范围查询（回测主循环最常用）
    3. idx_stock_daily_date: 仅日期索引，用于快速日期过滤
    4. idx_stock_info_code: stock_info 表的主键索引，优化 JOIN
    
    Args:
        conn: SQLite 连接对象
        defer_analyze: 是否延迟执行 ANALYZE（推荐 True，避免阻塞启动）
    """
    cur = conn.cursor()
    
    # CHANGED: 优化索引定义，确保覆盖所有常用查询模式
    indexes = [
        # 1. 覆盖 (stock_code, trade_date) 精确查询（单股票历史数据）
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date ON stock_daily(stock_code, trade_date)",
        
        # 2. 覆盖 (trade_date, stock_code) 查询（回测主循环：按日期获取股票池）
        # 这个索引对 get_stock_pool 性能至关重要
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_date_code ON stock_daily(trade_date, stock_code)",
        
        # 3. 仅日期索引（用于快速日期范围查询和 DISTINCT trade_date）
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(trade_date)",
        
        # 4. stock_info 主键索引（优化 JOIN 性能）
        "CREATE INDEX IF NOT EXISTS idx_stock_info_code ON stock_info(stock_code)",
        
        # 5. CHANGED: 添加市值过滤索引（优化 get_stock_pool 中的 total_mv 过滤）
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_mv ON stock_daily(total_mv) WHERE total_mv IS NOT NULL",
        
        # 6. CHANGED: 添加成交量过滤索引（优化 volume > 0 过滤）
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_volume ON stock_daily(volume) WHERE volume > 0",

        "CREATE INDEX IF NOT EXISTS idx_stock_daily_date_mv_volume ON stock_daily(trade_date, total_mv, volume)",
        
        # 7. backtest_results 索引
        "CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy ON backtest_results(strategy_name)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_results_created ON backtest_results(created_at)",
        
        # 8. trade_records 索引
        "CREATE INDEX IF NOT EXISTS idx_trade_records_backtest ON trade_records(backtest_id)",
        "CREATE INDEX IF NOT EXISTS idx_trade_records_stock ON trade_records(stock_code)",
        "CREATE INDEX IF NOT EXISTS idx_trade_records_date ON trade_records(date)",
        
        # 9. optimization_results 索引
        "CREATE INDEX IF NOT EXISTS idx_optimization_backtest ON optimization_results(backtest_id)",
        "CREATE INDEX IF NOT EXISTS idx_optimization_strategy ON optimization_results(strategy_name)",
    ]
    
    for index_sql in indexes:
        try:
            cur.execute(index_sql)
        except sqlite3.Error as e:
            # CHANGED: 使用更详细的错误信息
            print(f"[WARN] 创建索引失败: {index_sql[:60]}... - {e}")
    
    conn.commit()
    
    # 【关键修复】注释掉 ANALYZE 执行（包括同步和后台）
    # 原因：对于1500万行的数据表，ANALYZE 需要扫描大量数据块，耗时30秒+
    # ANALYZE 操作在数据写入后做一次就够了，不应该在每次读数据前都做
    # 如果需要更新统计信息，应该手动执行，而不是自动执行
    # 
    # CHANGED: 延迟执行 ANALYZE，避免阻塞启动
    # if not defer_analyze:
    #     try:
    #         cur.execute("ANALYZE;")
    #         conn.commit()
    #         print("[DB] 索引 ANALYZE 完成")
    #     except sqlite3.Error as e:
    #         print(f"[WARN] 索引 ANALYZE 失败: {e}")
    # elif defer_analyze:
    #     # 在后台线程执行 ANALYZE
    #     import threading
    #     def _analyze_background():
    #         try:
    #             time.sleep(1.0)  # 延迟 1 秒，让索引创建完成
    #             cur.execute("ANALYZE;")
    #             conn.commit()
    #             print("[DB] 后台索引 ANALYZE 完成")
    #         except Exception as e:
    #             print(f"[WARN] 后台索引 ANALYZE 失败: {e}")
    #     
    #     threading.Thread(target=_analyze_background, daemon=True).start()


def ensure_tables(conn: sqlite3.Connection) -> None:
    """
    确保必要的数据库表存在，如果不存在则创建
    
    Args:
        conn: SQLite 连接对象
    """
    cur = conn.cursor()
    
    # 检查 stock_info 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_info'")
    if cur.fetchone() is None:
        print("[DB] 创建 stock_info 表...")
        cur.execute("""
            CREATE TABLE stock_info (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                industry TEXT,
                region TEXT,
                list_date DATE,
                is_st BOOLEAN DEFAULT 0,
                is_kc BOOLEAN DEFAULT 0,
                is_cy BOOLEAN DEFAULT 0
            )
        """)
    
    # 检查 stock_daily 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_daily'")
    if cur.fetchone() is None:
        print("[DB] 创建 stock_daily 表...")
        cur.execute("""
            CREATE TABLE stock_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                trade_date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                prev_close REAL,
                change_amount REAL,
                change_pct REAL,
                volume INTEGER,
                amount REAL,
                total_mv REAL,
                float_mv REAL,
                turnover_rate REAL,
                turnover_free REAL,
                volume_ratio REAL,
                pe REAL,
                pe_ttm REAL,
                pb REAL,
                ps REAL,
                ps_ttm REAL,
                dividend_yield REAL,
                dividend_yield_ttm REAL,
                total_shares REAL,
                float_shares REAL,
                free_float_shares REAL,
                limit_up REAL,
                limit_down REAL,
                adj_factor REAL,
                ts_code TEXT
            )
        """)
    
    # 检查 benchmark_data 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_data'")
    if cur.fetchone() is None:
        print("[DB] 创建 benchmark_data 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date DATE NOT NULL,
                close REAL NOT NULL,
                UNIQUE(code, date)
            )
        """)
    
    # 检查 backtest_results 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_results'")
    if cur.fetchone() is None:
        print("[DB] 创建 backtest_results 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                initial_capital REAL NOT NULL,
                final_capital REAL NOT NULL,
                total_return REAL NOT NULL,
                annual_return REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                sortino_ratio REAL NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL NOT NULL,
                trade_count INTEGER NOT NULL,
                params TEXT NOT NULL,  -- JSON 格式的参数
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # 检查 trade_records 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_records'")
    if cur.fetchone() is None:
        print("[DB] 创建 trade_records 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                action TEXT NOT NULL,  -- 'buy' 或 'sell'
                date DATE NOT NULL,
                price REAL NOT NULL,
                shares REAL NOT NULL,
                amount REAL NOT NULL,
                profit_loss REAL,
                FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
            )
        """)
    
    # 检查 optimization_results 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='optimization_results'")
    if cur.fetchone() is None:
        print("[DB] 创建 optimization_results 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                backtest_id INTEGER NOT NULL,
                params TEXT NOT NULL,  -- JSON 格式的参数
                score REAL NOT NULL,
                rank INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
            )
        """)
    
    conn.commit()


def create_readonly_connection(db_path: str) -> sqlite3.Connection:
    """
    创建只读共享缓存连接（适用于多线程读取）
    
    CHANGED: 使用只读共享缓存连接提升性能
    """
    try:
        # 尝试使用只读共享缓存连接
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro&cache=shared",
            uri=True,
            check_same_thread=False
        )
        apply_performance_pragmas(conn, read_only=True)
        return conn
    except sqlite3.Error:
        # 回退到普通只读连接
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            check_same_thread=False
        )
        apply_performance_pragmas(conn, read_only=True)
        return conn

