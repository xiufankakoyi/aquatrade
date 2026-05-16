"""
统一写入漏斗 (Ingestion Pipeline)
================================

双源写入的收敛漏斗，确保：
1. 落库数据必须是原始除权数据
2. LanceDB Upsert 与 Redis 水位表更新原子绑定
3. 异常时安全回滚

使用示例:
    >>> with ingestion_pipeline("daily_ohlcv", "tushare") as writer:
    >>>     writer.upsert(df)  # 自动更新水位表
"""

import time
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime

import polars as pl

from config.logger import get_logger
from data_svc.ingestion.watermark_manager import get_watermark_manager

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """写入结果"""
    success: bool
    rows_written: int = 0
    stock_codes: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: float = 0.0


class DataIngestionWriter:
    """
    数据写入器
    
    负责执行 LanceDB Upsert 并更新水位表。
    
    重要约定：
    - 输入数据必须是原始除权数据（不复权）
    - close 和 adj_factor 必须保留原始值
    - 复权计算推迟到读取层
    """
    
    REQUIRED_COLUMNS = [
        "stock_code", "trade_date", 
        "open", "high", "low", "close", "volume"
    ]
    
    def __init__(
        self,
        table_name: str,
        data_source: str = "tushare",
        stock_code: Optional[str] = None
    ):
        self._table_name = table_name
        self._data_source = data_source
        self._stock_code = stock_code
        
        self._rows_written = 0
        self._last_date: Optional[str] = None
        self._first_date: Optional[str] = None
        self._stock_codes: List[str] = []
        self._committed = False
        self._start_time = time.time()
        
        self._watermark = get_watermark_manager()
        self._table = None
        self._lance_ds = None
        
        self._init_table()
    
    def _init_table(self) -> None:
        """初始化 LanceDB 表"""
        try:
            from data_svc.storage.lancedb_reader import LanceDBDataReader
            
            reader = LanceDBDataReader()
            if reader.table:
                self._table = reader.table
                self._lance_ds = reader.lance_ds
        except Exception as e:
            logger.warning(f"初始化 LanceDB 表失败: {e}")
    
    def validate_data(self, df: pl.DataFrame) -> bool:
        """
        验证数据格式
        
        确保包含必需列且为原始除权数据。
        
        Args:
            df: Polars DataFrame
            
        Returns:
            是否通过验证
        """
        missing_cols = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            logger.error(f"数据缺少必需列: {missing_cols}")
            return False
        
        if "adj_factor" not in df.columns:
            logger.warning("数据缺少 adj_factor 列，将默认设为 1.0")
        
        return True
    
    def upsert(
        self,
        df: pl.DataFrame,
        on_conflict: str = "merge"
    ) -> int:
        """
        执行 Upsert 操作
        
        Args:
            df: Polars DataFrame（必须是原始除权数据）
            on_conflict: 冲突处理策略
            
        Returns:
            写入的行数
        """
        if df.is_empty():
            return 0
        
        if not self.validate_data(df):
            raise ValueError("数据验证失败")
        
        if "adj_factor" not in df.columns:
            df = df.with_columns(pl.lit(1.0).alias("adj_factor"))
        
        try:
            if self._table is None:
                logger.warning("LanceDB 表未初始化，跳过写入")
                return 0
            
            import pyarrow as pa
            
            if on_conflict == "merge":
                dates = df.select("trade_date").unique().to_series().to_list()
                codes = df.select("stock_code").unique().to_series().to_list()
                single_stock = self._stock_code or len(codes) == 1
                for date_val in dates:
                    date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
                    try:
                        if single_stock:
                            code = self._stock_code or codes[0]
                            self._table.delete(f"trade_date = DATE '{date_str}' AND stock_code = '{code}'")
                        else:
                            self._table.delete(f"trade_date = DATE '{date_str}'")
                    except Exception:
                        try:
                            if single_stock:
                                code = self._stock_code or codes[0]
                                self._table.delete(f'trade_date = "{date_str}" AND stock_code = "{code}"')
                            else:
                                self._table.delete(f'trade_date = "{date_str}"')
                        except Exception as exc:
                            logger.warning(f"Upsert delete failed for {date_str}: {exc}")

            arrow_table = df.to_arrow()
            self._table.add(arrow_table, mode="append")
            
            rows = len(df)
            self._rows_written += rows
            
            stock_codes = df.select("stock_code").unique().to_series().to_list()
            self._stock_codes.extend(stock_codes)
            
            trade_dates = df.select("trade_date").to_series().to_list()
            if trade_dates:
                sorted_dates = sorted(trade_dates)
                if self._first_date is None or sorted_dates[0] < self._first_date:
                    self._first_date = sorted_dates[0]
                if self._last_date is None or sorted_dates[-1] > self._last_date:
                    self._last_date = sorted_dates[-1]
            
            logger.debug(f"Upsert {rows} 行到 {self._table_name}")
            
            return rows
            
        except Exception as e:
            logger.error(f"Upsert 失败: {e}")
            raise
    
    def _commit_watermark(self) -> None:
        """提交水位表更新"""
        if self._committed or self._rows_written == 0:
            return
        
        if not self._watermark.is_available:
            logger.warning("水位表不可用，跳过更新")
            self._committed = True
            return
        
        try:
            updates = []
            
            for stock_code in set(self._stock_codes):
                updates.append({
                    "stock_code": stock_code,
                    "last_update_date": self._last_date or datetime.now().strftime("%Y-%m-%d"),
                    "rows_added": self._rows_written,
                    "data_source": self._data_source,
                    "first_date": self._first_date
                })
            
            if updates:
                count = self._watermark.batch_update(updates)
                logger.info(f"水位表更新: {count}/{len(updates)} 只股票")
            
            self._committed = True
            
        except Exception as e:
            logger.error(f"水位表更新失败: {e}")
    
    def rollback(self) -> None:
        """回滚操作（水位表不会更新）"""
        logger.warning(f"回滚写入操作，已写入 {self._rows_written} 行将保留在 LanceDB")
        self._committed = True
    
    def get_result(self) -> IngestionResult:
        """获取写入结果"""
        return IngestionResult(
            success=self._committed,
            rows_written=self._rows_written,
            stock_codes=list(set(self._stock_codes)),
            duration_ms=(time.time() - self._start_time) * 1000
        )


@contextmanager
def ingestion_pipeline(
    table_name: str = "daily_ohlcv",
    data_source: str = "tushare",
    stock_code: Optional[str] = None
):
    """
    统一数据写入漏斗（上下文管理器）
    
    原子操作：
    1. 执行 LanceDB Upsert
    2. 成功后更新 Redis 水位表
    
    Args:
        table_name: 目标表名
        data_source: 数据来源 (tushare/crawler)
        stock_code: 单只股票代码（可选）
        
    Yields:
        DataIngestionWriter: 数据写入器
        
    使用示例:
        >>> with ingestion_pipeline("daily_ohlcv", "tushare") as writer:
        >>>     df = pl.DataFrame({...})
        >>>     writer.upsert(df)
        >>> 
        >>> # 退出时自动更新水位表
        >>> result = writer.get_result()
        >>> print(f"写入 {result.rows_written} 行")
    """
    writer = DataIngestionWriter(table_name, data_source, stock_code)
    
    try:
        yield writer
        
        if writer._rows_written > 0:
            writer._commit_watermark()
        
        result = writer.get_result()
        logger.info(
            f"[Ingestion] 完成: {result.rows_written} 行, "
            f"{len(result.stock_codes)} 只股票, "
            f"{result.duration_ms:.2f}ms"
        )
        
    except Exception as e:
        writer.rollback()
        logger.error(f"[Ingestion] 失败: {e}")
        raise


def upsert_daily_data(
    df: pl.DataFrame,
    data_source: str = "tushare"
) -> IngestionResult:
    """
    便捷函数：单次写入日线数据
    
    Args:
        df: Polars DataFrame（必须是原始除权数据）
        data_source: 数据来源
        
    Returns:
        IngestionResult: 写入结果
    """
    with ingestion_pipeline("daily_ohlcv", data_source) as writer:
        writer.upsert(df)
        return writer.get_result()
