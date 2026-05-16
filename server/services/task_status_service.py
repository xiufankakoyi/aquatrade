"""
任务状态管理服务
===============

【功能说明】
管理 Celery 任务的实时状态，支持：
1. 任务状态查询
2. 任务结果缓存
3. 任务取消
4. 任务进度订阅（Redis Pub/Sub）

【使用场景】
- HTTP API 轮询任务状态
- SocketIO 实时推送任务进度
- Worker 进程更新任务进度
"""
import json
import threading
import time
from typing import Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import redis
from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)


class TaskState(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskInfo:
    """任务信息数据类"""
    task_id: str
    task_type: str  # 'backtest', 'optimization', 'data'
    state: TaskState
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'state': self.state.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'meta': self.meta,
        }


class TaskStatusService:
    """
    任务状态管理服务
    
    单例模式，管理所有异步任务的状态。
    """
    
    _instance: Optional['TaskStatusService'] = None
    _lock = threading.Lock()
    
    # Redis Key 前缀
    TASK_KEY_PREFIX = "task:"
    TASK_CHANNEL_PREFIX = "task:channel:"
    TASK_RESULT_PREFIX = "task:result:"
    
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
        
        # 本地任务缓存（用于快速查询）
        self._local_tasks: Dict[str, TaskInfo] = {}
        self._local_lock = threading.RLock()
        
        # Redis 客户端
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        
        # 订阅回调
        self._subscribers: Dict[str, Set[Callable]] = {}
        self._subscriber_lock = threading.RLock()
        
        # 初始化 Redis 连接
        self._init_redis()
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            self._redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
            self._redis.ping()
            self.logger.info("TaskStatusService Redis 连接成功")
        except Exception as e:
            self.logger.warning(f"TaskStatusService Redis 连接失败: {e}，将使用本地缓存")
            self._redis = None
    
    def _get_redis(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端（带重连）"""
        if self._redis is None:
            return None
        try:
            self._redis.ping()
            return self._redis
        except:
            self._init_redis()
            return self._redis
    
    def _get_task_key(self, task_id: str) -> str:
        """获取任务状态 Redis Key"""
        return f"{self.TASK_KEY_PREFIX}{task_id}"
    
    def _get_channel_name(self, task_id: str) -> str:
        """获取任务频道名称"""
        return f"{self.TASK_CHANNEL_PREFIX}{task_id}"
    
    def _get_result_key(self, task_id: str) -> str:
        """获取任务结果 Redis Key"""
        return f"{self.TASK_RESULT_PREFIX}{task_id}"
    
    def register_task(self, task_id: str, task_type: str, meta: Dict[str, Any] = None) -> TaskInfo:
        """
        注册新任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            meta: 额外元数据
            
        Returns:
            TaskInfo: 任务信息
        """
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            state=TaskState.PENDING,
            created_at=datetime.now(),
            meta=meta or {}
        )
        
        # 本地缓存
        with self._local_lock:
            self._local_tasks[task_id] = task_info
        
        # Redis 缓存
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = self._get_task_key(task_id)
                redis_client.setex(
                    key,
                    3600 * 24,  # 24小时过期
                    json.dumps(task_info.to_dict())
                )
            except Exception as e:
                self.logger.warning(f"Redis 任务注册失败: {e}")
        
        self.logger.debug(f"任务已注册: {task_id} ({task_type})")
        return task_info
    
    def update_task_state(self, task_id: str, state: TaskState, **kwargs):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            state: 新状态
            **kwargs: 其他更新字段
        """
        with self._local_lock:
            if task_id in self._local_tasks:
                task = self._local_tasks[task_id]
                task.state = state
                
                if state == TaskState.STARTED:
                    task.started_at = datetime.now()
                elif state in [TaskState.SUCCESS, TaskState.FAILURE, TaskState.CANCELLED]:
                    task.completed_at = datetime.now()
                
                if 'progress' in kwargs:
                    task.progress.update(kwargs.pop('progress'))
                if 'result' in kwargs:
                    task.result = kwargs.pop('result')
                if 'error' in kwargs:
                    task.error = kwargs.pop('error')
                if 'meta' in kwargs:
                    task.meta.update(kwargs.pop('meta'))
                
                task_data = task.to_dict()
            else:
                self.logger.warning(f"更新状态失败，任务不存在: {task_id}")
                return
        
        # 更新 Redis
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = self._get_task_key(task_id)
                redis_client.setex(key, 3600 * 24, json.dumps(task_data))
                
                # 发布状态更新
                channel = self._get_channel_name(task_id)
                redis_client.publish(channel, json.dumps({
                    'type': 'state_update',
                    'task_id': task_id,
                    'data': task_data
                }))
            except Exception as e:
                self.logger.warning(f"Redis 状态更新失败: {e}")
        
        # 触发本地订阅回调
        self._notify_subscribers(task_id, task_data)
    
    def update_progress(self, task_id: str, current: int, total: int = 100, message: str = "", **kwargs):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            current: 当前进度
            total: 总进度
            message: 进度消息
            **kwargs: 额外进度数据
        """
        progress_data = {
            'current': current,
            'total': total,
            'percent': int((current / total) * 100) if total > 0 else 0,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }
        progress_data.update(kwargs)
        
        self.update_task_state(task_id, TaskState.PROGRESS, progress=progress_data)
        
        # 单独发布进度更新
        redis_client = self._get_redis()
        if redis_client:
            try:
                channel = self._get_channel_name(task_id)
                redis_client.publish(channel, json.dumps({
                    'type': 'progress',
                    'task_id': task_id,
                    'data': progress_data
                }))
            except Exception as e:
                self.logger.warning(f"Redis 进度发布失败: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            TaskInfo: 任务信息，不存在返回 None
        """
        # 先查本地缓存
        with self._local_lock:
            if task_id in self._local_tasks:
                return self._local_tasks[task_id]
        
        # 再查 Redis
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = self._get_task_key(task_id)
                data = redis_client.get(key)
                if data:
                    task_dict = json.loads(data)
                    # 转换为 TaskInfo
                    task_info = TaskInfo(
                        task_id=task_dict['task_id'],
                        task_type=task_dict['task_type'],
                        state=TaskState(task_dict['state']),
                        created_at=datetime.fromisoformat(task_dict['created_at']) if task_dict.get('created_at') else None,
                        started_at=datetime.fromisoformat(task_dict['started_at']) if task_dict.get('started_at') else None,
                        completed_at=datetime.fromisoformat(task_dict['completed_at']) if task_dict.get('completed_at') else None,
                        progress=task_dict.get('progress', {}),
                        result=task_dict.get('result'),
                        error=task_dict.get('error'),
                        meta=task_dict.get('meta', {}),
                    )
                    # 缓存到本地
                    with self._local_lock:
                        self._local_tasks[task_id] = task_info
                    return task_info
            except Exception as e:
                self.logger.warning(f"Redis 查询失败: {e}")
        
        return None
    
    def store_result(self, task_id: str, result: Any, expire: int = 3600 * 24):
        """
        存储任务结果（大结果单独存储）
        
        Args:
            task_id: 任务ID
            result: 结果数据
            expire: 过期时间（秒）
        """
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = self._get_result_key(task_id)
                redis_client.setex(key, expire, json.dumps(result))
            except Exception as e:
                self.logger.warning(f"Redis 结果存储失败: {e}")
    
    def get_result(self, task_id: str) -> Optional[Any]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Any: 结果数据
        """
        # 先查本地
        with self._local_lock:
            if task_id in self._local_tasks:
                task = self._local_tasks[task_id]
                if task.result is not None:
                    return task.result
        
        # 再查 Redis
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = self._get_result_key(task_id)
                data = redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                self.logger.warning(f"Redis 结果查询失败: {e}")
        
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        from config.celery_config import revoke_task
        
        # 调用 Celery 取消
        success = revoke_task(task_id)
        
        if success:
            self.update_task_state(task_id, TaskState.CANCELLED)
        
        return success
    
    def subscribe(self, task_id: str, callback: Callable[[Dict], None]):
        """
        订阅任务状态更新
        
        Args:
            task_id: 任务ID
            callback: 回调函数，接收状态字典
        """
        with self._subscriber_lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = set()
            self._subscribers[task_id].add(callback)
    
    def unsubscribe(self, task_id: str, callback: Callable[[Dict], None]):
        """
        取消订阅
        
        Args:
            task_id: 任务ID
            callback: 回调函数
        """
        with self._subscriber_lock:
            if task_id in self._subscribers:
                self._subscribers[task_id].discard(callback)
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]
    
    def _notify_subscribers(self, task_id: str, data: Dict):
        """通知订阅者"""
        with self._subscriber_lock:
            callbacks = self._subscribers.get(task_id, set()).copy()
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.warning(f"订阅回调执行失败: {e}")
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        清理过期任务
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self._local_lock:
            to_remove = [
                task_id for task_id, task in self._local_tasks.items()
                if task.created_at.timestamp() < cutoff
            ]
            for task_id in to_remove:
                del self._local_tasks[task_id]
        
        self.logger.info(f"清理了 {len(to_remove)} 个过期任务")


# 全局服务实例
_task_status_service: Optional[TaskStatusService] = None


def get_task_status_service() -> TaskStatusService:
    """获取任务状态服务单例"""
    global _task_status_service
    if _task_status_service is None:
        _task_status_service = TaskStatusService()
    return _task_status_service
