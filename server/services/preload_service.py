"""
回测预加载服务
负责在用户 hover 按钮时静默预加载策略代码和数据缓存
"""
import hashlib
import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config.logger import get_logger


@dataclass
class PreloadTask:
    """预加载任务"""
    task_id: str
    strategy_name: str
    start_date: str
    end_date: str
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    cache_key: Optional[str] = None


class PreloadService:
    """
    回测预加载服务
    
    功能:
    - 预加载策略代码（向量化）
    - 预热数据缓存（K线数据）
    - 缓存股票池
    
    使用场景:
    - 用户 hover "运行回测" 按钮时触发
    - 预加载完成后，实际回测可以直接使用缓存
    """
    
    _instance: Optional['PreloadService'] = None
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
        self._tasks: Dict[str, PreloadTask] = {}
        self._cache: Dict[str, Any] = {}
        self._max_cache_size = 10
    
    def _generate_task_id(self, strategy_name: str, start_date: str, end_date: str) -> str:
        """生成任务 ID"""
        key = f"{strategy_name}:{start_date}:{end_date}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    def _generate_cache_key(self, strategy_name: str, start_date: str, end_date: str) -> str:
        """生成缓存 Key"""
        return f"preload:{strategy_name}:{start_date}:{end_date}"
    
    def preload_strategy(self, strategy_name: str, start_date: str, end_date: str) -> PreloadTask:
        """
        预加载策略和数据
        
        Args:
            strategy_name: 策略名称
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            PreloadTask: 预加载任务
        """
        task_id = self._generate_task_id(strategy_name, start_date, end_date)
        
        if task_id in self._tasks:
            existing_task = self._tasks[task_id]
            if existing_task.status == "completed":
                return existing_task
            elif existing_task.status == "loading":
                return existing_task
        
        task = PreloadTask(
            task_id=task_id,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            status="loading"
        )
        self._tasks[task_id] = task
        
        thread = threading.Thread(
            target=self._execute_preload,
            args=(task,),
            daemon=True
        )
        thread.start()
        
        return task
    
    def _execute_preload(self, task: PreloadTask):
        """执行预加载"""
        try:
            self.logger.info(f"[Preload] 开始预加载: {task.strategy_name} ({task.start_date} ~ {task.end_date})")
            start_time = time.time()
            
            cache_key = self._generate_cache_key(task.strategy_name, task.start_date, task.end_date)
            
            if cache_key in self._cache:
                task.status = "completed"
                task.cache_key = cache_key
                task.completed_at = datetime.now()
                self.logger.info(f"[Preload] 命中缓存: {task.task_id}")
                return
            
            self._preload_strategy_code(task.strategy_name)
            
            self._preload_data_cache(task.start_date, task.end_date)
            
            self._preload_stock_pool(task.start_date)
            
            self._cleanup_old_cache()
            
            self._cache[cache_key] = {
                "strategy_name": task.strategy_name,
                "start_date": task.start_date,
                "end_date": task.end_date,
                "loaded_at": datetime.now().isoformat()
            }
            
            task.status = "completed"
            task.cache_key = cache_key
            task.completed_at = datetime.now()
            
            duration = time.time() - start_time
            self.logger.info(f"[Preload] 预加载完成: {task.task_id} ({duration:.2f}s)")
            
        except Exception as e:
            task.status = "error"
            task.error = str(e)
            self.logger.error(f"[Preload] 预加载失败: {task.task_id} - {e}")
    
    def _preload_strategy_code(self, strategy_name: str):
        """预加载策略代码"""
        try:
            from core.strategies.strategy_factory import get_factory
            factory = get_factory()
            
            strategy = factory.create_strategy(strategy_name, use_simple=True)
            if strategy is None:
                self.logger.warning(f"[Preload] 策略未找到: {strategy_name}")
                return
            
            if hasattr(strategy, 'initialize'):
                try:
                    strategy.initialize()
                except Exception as e:
                    self.logger.debug(f"[Preload] 策略初始化跳过: {e}")
            
            self.logger.debug(f"[Preload] 策略代码已加载: {strategy_name}")
            
        except Exception as e:
            self.logger.warning(f"[Preload] 策略预加载失败: {e}")
    
    def _preload_data_cache(self, start_date: str, end_date: str):
        """预热数据缓存"""
        try:
            from data_svc.database.optimized_data_query import OptimizedStockDataQuery
            
            data_query = OptimizedStockDataQuery(warmup=False)
            
            trading_dates = data_query.get_trading_dates(start_date, end_date)
            if trading_dates:
                self.logger.debug(f"[Preload] 交易日已缓存: {len(trading_dates)} 天")
            
            try:
                stock_pool = data_query.get_stock_pool(start_date)
                if stock_pool is not None and len(stock_pool) > 0:
                    self.logger.debug(f"[Preload] 股票池已缓存: {len(stock_pool)} 只")
            except Exception as e:
                self.logger.debug(f"[Preload] 股票池预加载跳过: {e}")
            
        except Exception as e:
            self.logger.warning(f"[Preload] 数据缓存预热失败: {e}")
    
    def _preload_stock_pool(self, date: str):
        """预加载股票池"""
        try:
            from data_svc.database.optimized_data_query import OptimizedStockDataQuery
            
            data_query = OptimizedStockDataQuery(warmup=False)
            stock_pool = data_query.get_stock_pool(date)
            
            if stock_pool is not None:
                self.logger.debug(f"[Preload] 股票池预加载完成: {len(stock_pool)} 只")
            
        except Exception as e:
            self.logger.debug(f"[Preload] 股票池预加载跳过: {e}")
    
    def _cleanup_old_cache(self):
        """清理旧缓存"""
        if len(self._cache) > self._max_cache_size:
            keys_to_remove = list(self._cache.keys())[:-self._max_cache_size]
            for key in keys_to_remove:
                del self._cache[key]
                self.logger.debug(f"[Preload] 清理缓存: {key}")
    
    def get_task_status(self, task_id: str) -> Optional[PreloadTask]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def is_preloaded(self, strategy_name: str, start_date: str, end_date: str) -> bool:
        """检查是否已预加载"""
        cache_key = self._generate_cache_key(strategy_name, start_date, end_date)
        return cache_key in self._cache
    
    def get_preload_cache(self, strategy_name: str, start_date: str, end_date: str) -> Optional[Any]:
        """获取预加载缓存"""
        cache_key = self._generate_cache_key(strategy_name, start_date, end_date)
        return self._cache.get(cache_key)


_preload_service: Optional[PreloadService] = None


def get_preload_service() -> PreloadService:
    """获取预加载服务单例"""
    global _preload_service
    if _preload_service is None:
        _preload_service = PreloadService()
    return _preload_service
