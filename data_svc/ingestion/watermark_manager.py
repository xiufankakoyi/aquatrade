"""
水位表管理器 (Watermark Manager)
================================

Redis 水位表管理，实现 O(1) 复杂度的数据巡查。

存储结构：
- watermark:daily -> Hash{stock_code: json_metadata}
- watermark:meta -> Hash{全局元数据}

水位表字段：
- stock_code: 股票代码
- last_update_date: 最后更新日期
- rows_added: 新增行数
- data_source: 数据来源 (tushare/crawler)
- first_date: 数据起始日期
- last_sync_ts: 最后同步时间戳
- checksum: 数据校验和（可选）
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
import threading

from config.logger import get_logger

logger = get_logger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


WATERMARK_KEY = "watermark:daily"
WATERMARK_META_KEY = "watermark:meta"
MAX_RECONCILE_BATCH = 100


class WatermarkManager:
    """
    水位表管理器
    
    线程安全的 Redis 水位表操作封装。
    
    使用示例:
        >>> wm = get_watermark_manager()
        >>> 
        >>> # 更新水位
        >>> wm.update("000001.SZ", "2026-04-25", rows_added=1, data_source="tushare")
        >>> 
        >>> # 获取水位
        >>> meta = wm.get("000001.SZ")
        >>> 
        >>> # 批量检查缺口
        >>> gaps = wm.check_gaps(trading_dates)
    """
    
    _instance: Optional['WatermarkManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls, redis_url: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, redis_url: Optional[str] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._local_lock = threading.RLock()
        
        self._init_redis()
    
    def _init_redis(self) -> None:
        """初始化 Redis 连接"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis 不可用，水位表功能降级为内存模式")
            return
        
        try:
            from config.config import Config
            redis_url = self._redis_url or Config.REDIS_URL
            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("水位表 Redis 连接成功")
        except Exception as e:
            logger.warning(f"水位表 Redis 连接失败: {e}")
            self._redis = None
    
    @property
    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        return self._redis is not None
    
    def get(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票的水位信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            水位元数据字典，不存在返回 None
        """
        if not self.is_available:
            return None
        
        try:
            data = self._redis.hget(WATERMARK_KEY, stock_code)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"获取水位失败 {stock_code}: {e}")
        
        return None
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有股票的水位信息
        
        Returns:
            {stock_code: metadata, ...}
        """
        if not self.is_available:
            return {}
        
        try:
            all_data = self._redis.hgetall(WATERMARK_KEY)
            return {
                code: json.loads(data)
                for code, data in all_data.items()
            }
        except Exception as e:
            logger.warning(f"获取全部水位失败: {e}")
            return {}
    
    def update(
        self,
        stock_code: str,
        last_update_date: str,
        rows_added: int = 1,
        data_source: str = "tushare",
        first_date: Optional[str] = None,
        checksum: Optional[str] = None
    ) -> bool:
        """
        更新水位表
        
        Args:
            stock_code: 股票代码
            last_update_date: 最后更新日期
            rows_added: 新增行数
            data_source: 数据来源
            first_date: 数据起始日期（首次写入时需要）
            checksum: 数据校验和
            
        Returns:
            是否更新成功
        """
        if not self.is_available:
            return False
        
        with self._local_lock:
            try:
                existing = self.get(stock_code)
                
                if existing:
                    metadata = existing.copy()
                    metadata["last_update_date"] = last_update_date
                    metadata["rows_added"] = existing.get("rows_added", 0) + rows_added
                    metadata["last_sync_ts"] = time.time()
                    metadata["data_source"] = data_source
                    
                    if checksum:
                        metadata["checksum"] = checksum
                else:
                    metadata = {
                        "stock_code": stock_code,
                        "last_update_date": last_update_date,
                        "rows_added": rows_added,
                        "data_source": data_source,
                        "first_date": first_date or last_update_date,
                        "last_sync_ts": time.time(),
                        "checksum": checksum or ""
                    }
                
                self._redis.hset(WATERMARK_KEY, stock_code, json.dumps(metadata))
                
                self._update_meta_stats()
                
                return True
                
            except Exception as e:
                logger.error(f"更新水位失败 {stock_code}: {e}")
                return False
    
    def batch_update(
        self,
        updates: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新水位表
        
        Args:
            updates: 更新列表，每个元素包含 stock_code, last_update_date 等
            
        Returns:
            成功更新的数量
        """
        if not self.is_available:
            return 0
        
        success_count = 0
        
        with self._local_lock:
            try:
                pipe = self._redis.pipeline()
                
                for update in updates:
                    stock_code = update["stock_code"]
                    
                    last_date = update["last_update_date"]
                    if hasattr(last_date, 'strftime'):
                        last_date = last_date.strftime("%Y-%m-%d")
                    
                    first_date = update.get("first_date", last_date)
                    if hasattr(first_date, 'strftime'):
                        first_date = first_date.strftime("%Y-%m-%d")
                    
                    metadata = {
                        "stock_code": stock_code,
                        "last_update_date": last_date,
                        "rows_added": update.get("rows_added", 1),
                        "data_source": update.get("data_source", "tushare"),
                        "first_date": first_date,
                        "last_sync_ts": time.time(),
                        "checksum": update.get("checksum", "")
                    }
                    pipe.hset(WATERMARK_KEY, stock_code, json.dumps(metadata))
                    success_count += 1
                
                pipe.execute()
                
                self._update_meta_stats()
                
            except Exception as e:
                logger.error(f"批量更新水位失败: {e}")
        
        return success_count
    
    def delete(self, stock_code: str) -> bool:
        """删除水位记录"""
        if not self.is_available:
            return False
        
        try:
            self._redis.hdel(WATERMARK_KEY, stock_code)
            return True
        except Exception as e:
            logger.warning(f"删除水位失败 {stock_code}: {e}")
            return False
    
    def clear_all(self) -> bool:
        """清空水位表（谨慎使用）"""
        if not self.is_available:
            return False
        
        try:
            self._redis.delete(WATERMARK_KEY)
            self._redis.delete(WATERMARK_META_KEY)
            logger.warning("水位表已清空")
            return True
        except Exception as e:
            logger.error(f"清空水位表失败: {e}")
            return False
    
    def check_gaps(
        self,
        trading_dates: List[str],
        stock_codes: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        检查数据缺口
        
        Args:
            trading_dates: 交易日历列表（已排序）
            stock_codes: 要检查的股票列表（None 表示全部）
            
        Returns:
            {stock_code: [missing_date1, missing_date2, ...], ...}
        """
        if not self.is_available or not trading_dates:
            return {}
        
        gaps = {}
        latest_trading_date = trading_dates[-1]
        
        try:
            all_watermarks = self.get_all()
            
            codes_to_check = stock_codes or list(all_watermarks.keys())
            
            for stock_code in codes_to_check:
                metadata = all_watermarks.get(stock_code)
                
                if not metadata:
                    gaps[stock_code] = trading_dates.copy()
                    continue
                
                last_update = metadata.get("last_update_date", "")
                
                if last_update < latest_trading_date:
                    missing = self._find_missing_dates(
                        last_update,
                        latest_trading_date,
                        trading_dates
                    )
                    if missing:
                        gaps[stock_code] = missing
                        
        except Exception as e:
            logger.error(f"检查数据缺口失败: {e}")
        
        return gaps
    
    def _find_missing_dates(
        self,
        start_date: str,
        end_date: str,
        trading_dates: List[str]
    ) -> List[str]:
        """找出缺失的交易日"""
        try:
            start_idx = trading_dates.index(start_date) if start_date in trading_dates else -1
            end_idx = trading_dates.index(end_date) if end_date in trading_dates else len(trading_dates) - 1
            
            if start_idx >= 0:
                return trading_dates[start_idx + 1:end_idx + 1]
            else:
                return []
        except ValueError:
            return []
    
    def _update_meta_stats(self) -> None:
        """更新全局元数据统计"""
        if not self.is_available:
            return
        
        try:
            count = self._redis.hlen(WATERMARK_KEY)
            self._redis.hset(WATERMARK_META_KEY, "total_stocks", str(count))
            self._redis.hset(WATERMARK_META_KEY, "last_update", datetime.now().isoformat())
        except Exception:
            pass
    
    def reconcile_from_lancedb(
        self,
        table_name: str = "daily_ohlcv",
        stock_codes: Optional[List[str]] = None,
        batch_size: int = MAX_RECONCILE_BATCH
    ) -> int:
        """
        从 LanceDB 重建水位表
        
        Args:
            table_name: 表名
            stock_codes: 指定股票列表（None 表示全部）
            batch_size: 批量处理大小
            
        Returns:
            重建的股票数量
        """
        if not self.is_available:
            logger.warning("Redis 不可用，无法重建水位表")
            return 0
        
        logger.info(f"开始从 LanceDB 重建水位表: {table_name}")
        
        try:
            from data_svc.storage.lancedb_reader import LanceDBDataReader
            
            reader = LanceDBDataReader()
            
            if not reader.table:
                logger.warning("LanceDB 表不存在")
                return 0
            
            import polars as pl
            
            df = reader.table.to_lance().to_table(
                columns=["stock_code", "trade_date"]
            ).to_pandas()
            
            if df.empty:
                logger.warning("LanceDB 表为空")
                return 0
            
            grouped = df.groupby("stock_code").agg({
                "trade_date": ["min", "max", "count"]
            })
            
            grouped.columns = ["first_date", "last_date", "rows"]
            grouped = grouped.reset_index()
            
            updates = []
            for _, row in grouped.iterrows():
                stock_code = row["stock_code"]
                
                if stock_codes and stock_code not in stock_codes:
                    continue
                
                updates.append({
                    "stock_code": stock_code,
                    "last_update_date": row["last_date"],
                    "rows_added": int(row["rows"]),
                    "data_source": "reconciled",
                    "first_date": row["first_date"]
                })
                
                if len(updates) >= batch_size:
                    self.batch_update(updates)
                    updates = []
            
            if updates:
                self.batch_update(updates)
            
            logger.info(f"水位表重建完成，共 {len(grouped)} 只股票")
            return len(grouped)
            
        except Exception as e:
            logger.error(f"重建水位表失败: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取水位表统计信息"""
        if not self.is_available:
            return {"available": False}
        
        try:
            return {
                "available": True,
                "total_stocks": self._redis.hlen(WATERMARK_KEY),
                "meta": self._redis.hgetall(WATERMARK_META_KEY)
            }
        except Exception as e:
            return {"available": False, "error": str(e)}


def get_watermark_manager(redis_url: Optional[str] = None) -> WatermarkManager:
    """获取水位表管理器单例"""
    return WatermarkManager(redis_url)
