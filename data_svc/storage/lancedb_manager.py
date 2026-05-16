"""
LanceDB 写入层管理器
====================

替代 ArcticDB，提供统一的写入接口。

核心特性:
1. 单表存储: 所有股票数据存储在一张表中
2. 索引加速: 为 date 字段创建标量索引
3. 零拷贝: Arrow Table 直接写入
4. 增量更新: 删除+追加模式

架构位置:
┌─────────────────────────────────────────────────────────────────┐
│                        写入层 (LanceDB)                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ • 单表存储所有股票数据                                      │ │
│  │ • 标量索引加速日期范围查询                                  │ │
│  │ • Arrow 零拷贝写入                                         │ │
│  │ • 增量更新 (删除+追加)                                      │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
"""

from pathlib import Path
from typing import Optional, List, Dict, Union, Any
from datetime import datetime, date
import polars as pl
import pyarrow as pa
from loguru import logger

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logger.warning("LanceDB not installed. Run: pip install lancedb")


class LanceDBManager:
    """
    LanceDB 写入层管理器
    
    核心功能:
    1. 单表存储: 所有股票数据存储在一张表中
    2. 索引加速: 为 date 字段创建标量索引
    3. 零拷贝: Arrow Table 直接写入
    4. 增量更新: 删除+追加模式
    
    使用示例:
        >>> manager = LanceDBManager("data/lancedb")
        >>> df = pl.DataFrame({...})  # 包含 symbol, date, OHLCV 列
        >>> manager.write_daily_data(df)
    """
    
    TABLE_NAME = "daily_ohlcv"
    
    EXPECTED_SCHEMA = {
        "stock_code": pa.string(),
        "trade_date": pa.string(),
        "open": pa.float64(),
        "high": pa.float64(),
        "low": pa.float64(),
        "close": pa.float64(),
        "volume": pa.float64(),
        "amount": pa.float64(),
    }
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 LanceDB 连接
        
        Args:
            db_path: 数据库路径，默认 data/lancedb
        """
        if not LANCEDB_AVAILABLE:
            raise ImportError(
                "LanceDB is required. Install with: pip install lancedb"
            )
        
        if db_path is None:
            from config.config import Config
            db_path = getattr(Config, 'LANCEDB_PATH', None)
            if db_path is None:
                project_root = Path(__file__).parent.parent.parent
                db_path = str(project_root / "data" / "lancedb")
        
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self._db = None
        self._table = None
        
        self._connect()
        
        logger.info(f"[LanceDBManager] 初始化完成，路径: {self.db_path}")
    
    def _connect(self) -> None:
        """建立 LanceDB 连接"""
        try:
            self._db = lancedb.connect(str(self.db_path))
            logger.info(f"[LanceDBManager] 已连接到数据库")
        except Exception as e:
            logger.error(f"[LanceDBManager] 连接失败: {e}")
            raise
    
    @property
    def db(self):
        """获取数据库实例"""
        if self._db is None:
            self._connect()
        return self._db
    
    @property
    def table(self):
        """获取表实例（延迟加载）"""
        if self._table is None:
            if self.TABLE_NAME in self.db.table_names():
                self._table = self.db.open_table(self.TABLE_NAME)
        return self._table
    
    def _ensure_table_exists(self, sample_df: pl.DataFrame) -> None:
        """确保表存在"""
        if self.TABLE_NAME not in self.db.table_names():
            logger.info(f"[LanceDBManager] 创建表: {self.TABLE_NAME}")
            self._table = self.db.create_table(
                self.TABLE_NAME,
                sample_df.to_arrow()
            )
            self._create_indexes()
    
    def _create_indexes(self) -> None:
        """创建索引"""
        if self.table is None:
            return
        
        try:
            self.table.create_scalar_index("trade_date", replace=True)
            logger.info(f"[LanceDBManager] 创建索引: trade_date")
        except Exception as e:
            logger.warning(f"[LanceDBManager] 创建索引失败: {e}")
    
    def write_daily_data(
        self,
        df: Union[pl.DataFrame, pa.Table],
        mode: str = "append"
    ) -> int:
        """
        写入日线数据
        
        Args:
            df: 数据，Polars DataFrame 或 Arrow Table
            mode: 写入模式
                - "append": 追加数据
                - "overwrite": 覆盖整表
                - "upsert": 按日期+股票代码更新
                
        Returns:
            写入行数
        """
        if isinstance(df, pa.Table):
            df = pl.from_arrow(df)
        
        if df.is_empty():
            logger.warning("[LanceDBManager] 空数据，跳过写入")
            return 0
        
        required_cols = ["stock_code", "trade_date"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {missing}")
        
        df = self._normalize_schema(df)
        
        if mode == "overwrite":
            return self._write_overwrite(df)
        elif mode == "upsert":
            return self._write_upsert(df)
        else:
            return self._write_append(df)
    
    def _normalize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """规范化数据类型"""
        if "trade_date" in df.columns:
            dtype = df.schema["trade_date"]
            if dtype == pl.Date:
                pass
            elif dtype == pl.Datetime:
                df = df.with_columns(
                    pl.col("trade_date").dt.date()
                )
            else:
                df = df.with_columns(
                    pl.col("trade_date").str.to_date()
                )
        
        float_cols = ["open", "high", "low", "close", "volume", "amount",
                      "change_pct", "turnover_rate", "total_mv", "float_mv"]
        for col in float_cols:
            if col in df.columns:
                df = df.with_columns(pl.col(col).cast(pl.Float64))
        
        return df
    
    def _write_append(self, df: pl.DataFrame) -> int:
        """追加写入"""
        self._ensure_table_exists(df)
        
        rows = len(df)
        self.table.add(df.to_arrow())
        
        logger.info(f"[LanceDBManager] 追加写入: {rows} 行")
        return rows
    
    def _write_overwrite(self, df: pl.DataFrame) -> int:
        """覆盖写入"""
        rows = len(df)
        
        if self.TABLE_NAME in self.db.table_names():
            self.db.drop_table(self.TABLE_NAME)
        
        self._table = self.db.create_table(
            self.TABLE_NAME,
            df.to_arrow()
        )
        self._create_indexes()
        
        logger.info(f"[LanceDBManager] 覆盖写入: {rows} 行")
        return rows
    
    def _write_upsert(self, df: pl.DataFrame) -> int:
        """
        按日期+股票代码更新
        
        先删除已存在的数据，再追加新数据
        """
        self._ensure_table_exists(df)
        
        dates = df.select("trade_date").unique()["trade_date"].to_list()
        codes = df.select("stock_code").unique()["stock_code"].to_list()
        
        deleted = 0
        for date_val in dates:
            try:
                self.table.delete(f'trade_date = "{date_val}"')
                deleted += 1
            except Exception as e:
                logger.debug(f"[LanceDBManager] 删除失败 {date_val}: {e}")
        
        rows = len(df)
        self.table.add(df.to_arrow())
        
        logger.info(f"[LanceDBManager] Upsert 写入: 删除 {deleted} 天数据, 追加 {rows} 行")
        return rows
    
    def delete_by_date(self, date_str: str) -> int:
        """
        删除指定日期的数据
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            删除的行数
        """
        if self.table is None:
            return 0
        
        try:
            before = self.table.count_rows(f'trade_date = "{date_str}"')
            self.table.delete(f'trade_date = "{date_str}"')
            logger.info(f"[LanceDBManager] 删除 {date_str}: {before} 行")
            return before
        except Exception as e:
            logger.error(f"[LanceDBManager] 删除失败: {e}")
            return 0
    
    def delete_by_symbol(self, symbol: str) -> int:
        """
        删除指定股票的数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            删除的行数
        """
        if self.table is None:
            return 0
        
        try:
            before = self.table.count_rows(f'stock_code = "{symbol}"')
            self.table.delete(f'stock_code = "{symbol}"')
            logger.info(f"[LanceDBManager] 删除 {symbol}: {before} 行")
            return before
        except Exception as e:
            logger.error(f"[LanceDBManager] 删除失败: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取表统计信息
        
        Returns:
            统计信息字典
        """
        if self.table is None:
            return {
                "table_exists": False,
                "row_count": 0,
            }
        
        try:
            total_rows = self.table.count_rows()
            
            dates = self.table.to_arrow().column("trade_date").to_pylist()
            unique_dates = len(set(dates)) if dates else 0
            
            codes = self.table.to_arrow().column("stock_code").to_pylist()
            unique_codes = len(set(codes)) if codes else 0
            
            return {
                "table_exists": True,
                "row_count": total_rows,
                "unique_dates": unique_dates,
                "unique_symbols": unique_codes,
                "db_path": str(self.db_path),
            }
        except Exception as e:
            logger.error(f"[LanceDBManager] 获取统计信息失败: {e}")
            return {
                "table_exists": True,
                "row_count": 0,
                "error": str(e),
            }
    
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 连接是否正常
        """
        try:
            _ = self.db.table_names()
            return True
        except Exception as e:
            logger.error(f"[LanceDBManager] 健康检查失败: {e}")
            return False
    
    def compact(self) -> None:
        """压缩表，优化存储"""
        if self.table is None:
            return
        
        try:
            self.table.compact_files()
            logger.info("[LanceDBManager] 表压缩完成")
        except Exception as e:
            logger.warning(f"[LanceDBManager] 表压缩失败: {e}")


_manager_instance: Optional[LanceDBManager] = None


def get_lancedb_manager(db_path: Optional[str] = None) -> LanceDBManager:
    """
    获取 LanceDBManager 单例
    
    Args:
        db_path: 数据库路径
        
    Returns:
        LanceDBManager 实例
    """
    global _manager_instance
    
    if _manager_instance is None:
        _manager_instance = LanceDBManager(db_path)
    
    return _manager_instance
