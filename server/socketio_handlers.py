"""
Socket.IO 事件处理器 (异步化改造版)
===================================

【架构说明】
本模块已改造为 Pub/Sub 模式：
1. SocketIO Handler 只负责接收前端请求和推送消息
2. 所有计算任务都提交给 Celery Worker
3. 通过 Redis Pub/Sub 接收 Worker 进度并转发给前端

【数据流】
前端 -> SocketIO Handler -> Celery Task -> Worker 计算
                                      |
                                      v
前端 <- SocketIO Handler <- Redis Pub/Sub
"""
import os
import json
import threading
import time
from typing import Dict, Any, Optional, Set
from threading import Event
from flask import request
from flask_socketio import emit

from config.logger import get_logger
from config.config import Config

logger = get_logger(__name__)


# ============================================================================
# Redis Pub/Sub 订阅管理器
# ============================================================================

class RedisPubSubManager:
    """
    Redis Pub/Sub 管理器
    
    管理 SocketIO 与 Redis 频道的订阅关系，
    将 Worker 发布的进度消息转发给前端。
    """
    
    _instance = None
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
        self._redis = None
        self._pubsub = None
        self._subscribed_channels: Set[str] = set()
        self._channel_sids: Dict[str, Set[str]] = {}  # channel -> set of sids
        self._lock = threading.RLock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        
        self._init_redis()
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import redis as redis_lib
            self._redis = redis_lib.from_url(Config.REDIS_URL, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            self._running = True
            
            # 启动监听线程
            self._listener_thread = threading.Thread(target=self._listen, daemon=True)
            self._listener_thread.start()
            
            logger.info("Redis Pub/Sub 管理器已启动")
        except Exception as e:
            logger.warning(f"Redis Pub/Sub 初始化失败: {e}")
            self._redis = None
            self._pubsub = None
    
    def _listen(self):
        """监听 Redis 消息"""
        if not self._pubsub:
            return
        
        logger.info("Redis Pub/Sub 监听线程已启动")
        
        for message in self._pubsub.listen():
            if not self._running:
                break
            
            if message['type'] == 'message':
                try:
                    channel = message['channel']
                    data = json.loads(message['data'])
                    
                    # 获取订阅此频道的所有 sid
                    with self._lock:
                        sids = self._channel_sids.get(channel, set()).copy()
                    
                    # 转发给所有订阅的 sid
                    self._forward_to_sids(channel, sids, data)
                    
                except Exception as e:
                    logger.warning(f"处理 Redis 消息失败: {e}")
    
    def _forward_to_sids(self, channel: str, sids: Set[str], data: Dict):
        """将消息转发给指定的 sid"""
        # 延迟导入避免循环依赖
        from server.socketio_manager import get_socketio
        
        socketio = get_socketio()
        if not socketio:
            return
        
        # 根据频道类型确定事件名
        if channel.startswith('backtest:'):
            event_type = data.get('type', 'backtest_update')
        elif channel.startswith('optimization:'):
            event_type = data.get('type', 'optimization_update')
        else:
            event_type = 'task_update'
        
        payload = data.get('data', data)
        
        for sid in sids:
            try:
                socketio.emit(event_type, payload, to=sid)
            except Exception as e:
                logger.warning(f"向 {sid} 发送消息失败: {e}")
    
    def subscribe(self, channel: str, sid: str):
        """
        订阅频道
        
        Args:
            channel: Redis 频道名
            sid: SocketIO 会话ID
        """
        if not self._pubsub:
            logger.warning("Redis Pub/Sub 不可用，无法订阅")
            return
        
        with self._lock:
            if channel not in self._subscribed_channels:
                self._pubsub.subscribe(channel)
                self._subscribed_channels.add(channel)
                self._channel_sids[channel] = set()
                logger.debug(f"订阅频道: {channel}")
            
            self._channel_sids[channel].add(sid)
            logger.debug(f"SID {sid} 订阅频道 {channel}")
    
    def unsubscribe(self, channel: str, sid: str):
        """
        取消订阅频道
        
        Args:
            channel: Redis 频道名
            sid: SocketIO 会话ID
        """
        if not self._pubsub:
            return
        
        with self._lock:
            if channel in self._channel_sids:
                self._channel_sids[channel].discard(sid)
                
                # 如果没有 sid 订阅此频道，取消订阅
                if not self._channel_sids[channel]:
                    self._pubsub.unsubscribe(channel)
                    self._subscribed_channels.discard(channel)
                    del self._channel_sids[channel]
                    logger.debug(f"取消订阅频道: {channel}")
    
    def unsubscribe_all(self, sid: str):
        """取消 sid 的所有订阅"""
        with self._lock:
            channels_to_remove = []
            for channel, sids in self._channel_sids.items():
                if sid in sids:
                    sids.discard(sid)
                    if not sids:
                        channels_to_remove.append(channel)
            
            for channel in channels_to_remove:
                if self._pubsub:
                    self._pubsub.unsubscribe(channel)
                self._subscribed_channels.discard(channel)
                del self._channel_sids[channel]


# 全局 Pub/Sub 管理器
_pubsub_manager: Optional[RedisPubSubManager] = None


def get_pubsub_manager() -> RedisPubSubManager:
    """获取 Pub/Sub 管理器单例"""
    global _pubsub_manager
    if _pubsub_manager is None:
        _pubsub_manager = RedisPubSubManager()
    return _pubsub_manager


# ============================================================================
# SocketIO 处理器注册
# ============================================================================

def register_socketio_handlers(socketio_instance):
    """
    注册所有 Socket.IO 事件处理器
    
    Args:
        socketio_instance: SocketIO 实例
    """
    # 延迟导入避免循环依赖
    from server.app import active_backtests, active_optimizations
    
    # 尝试导入 Celery 任务，如果失败则使用本地回退
    try:
        from server.tasks.backtest_tasks import (
            run_streaming_backtest_task, 
            run_optimization_task,
            cancel_backtest_task
        )
        CELERY_TASKS_AVAILABLE = True
    except ImportError as e:
        logger.warning(f"Celery 任务不可用，使用本地回退: {e}")
        CELERY_TASKS_AVAILABLE = False
        # 定义空函数作为回退
        def run_streaming_backtest_task(*args, **kwargs):
            raise RuntimeError("Celery 不可用，无法运行回测任务")
        def run_optimization_task(*args, **kwargs):
            raise RuntimeError("Celery 不可用，无法运行优化任务")
        def cancel_backtest_task(*args, **kwargs):
            pass
    
    pubsub_manager = get_pubsub_manager()
    
    @socketio_instance.on('connect')
    def handle_connect():
        """【健壮性加固】SocketIO 连接事件"""
        try:
            debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
            if debug_mode:
                logger.debug(f"Socket.IO 客户端已连接: {request.sid}")
        except Exception as e:
            logger.error(f"Socket.IO 连接处理失败: {e}")
    
    @socketio_instance.on('disconnect')
    def handle_disconnect():
        """【健壮性加固】SocketIO 断开事件"""
        try:
            sid = request.sid
            
            # 取消所有订阅
            pubsub_manager.unsubscribe_all(sid)
            
            # 清理活跃任务
            if sid in active_backtests:
                task_id = active_backtests[sid]
                cancel_backtest_task(task_id)
                del active_backtests[sid]
            
            if sid in active_optimizations:
                task_id = active_optimizations[sid]
                cancel_backtest_task(task_id)
                del active_optimizations[sid]
            
            debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
            if debug_mode:
                logger.debug(f"Socket.IO 客户端已断开: {sid}")
                
        except Exception as e:
            logger.error(f"Socket.IO 断开处理失败: {e}")
    
    @socketio_instance.on('run_streaming_backtest')
    def handle_streaming_backtest(data):
        """
        【异步化改造】处理流式回测请求
        
        不再直接执行回测，而是提交 Celery 任务，
        然后通过 Redis Pub/Sub 接收进度并转发给前端。
        """
        try:
            strategy_name = data.get('strategy_name')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            benchmark_code = data.get('benchmark_code')
            profile_id = data.get('profile_id')
            override_params = data.get('override_params') or {}
            
            # 回测配置参数
            initial_capital = data.get('initial_capital')
            commission = data.get('commission')
            slippage = data.get('slippage')

            if not all([strategy_name, start_date, end_date]):
                emit('backtest_error', {"message": "缺少必要参数"})
                return

            # 处理 profile 参数
            effective_params = None
            if profile_id is not None:
                try:
                    from core.profiles.profile_repository import get_profile as load_profile
                    profile = load_profile(int(profile_id))
                    if profile is None:
                        emit('backtest_error', {"message": f"Profile {profile_id} 不存在"})
                        return
                    params_from_profile = profile.get("params") or {}
                    if not isinstance(params_from_profile, dict):
                        params_from_profile = {}
                    if not isinstance(override_params, dict):
                        override_params = {}
                    effective_params = {**params_from_profile, **override_params}
                except Exception as e:
                    emit('backtest_error', {"message": f"加载 Profile 失败: {e}"})
                    return

            # 构建回测配置
            backtest_config = {
                'initial_capital': initial_capital,
                'commission': commission,
                'slippage': slippage
            }
            
            sid = request.sid
            channel = f"backtest:{sid}"
            
            logger.info(f"📨 [Async] 收到流式回测请求: {strategy_name} | {start_date}~{end_date} | sid: {sid}")

            # 订阅 Redis 频道
            pubsub_manager.subscribe(channel, sid)
            
            # 提交 Celery 任务
            task = run_streaming_backtest_task.delay(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                sid=sid,
                benchmark_code=benchmark_code,
                params=effective_params,
                backtest_config=backtest_config
            )
            
            # 记录活跃任务
            active_backtests[sid] = task.id
            
            # 给前端确认
            emit('request_received', {
                "message": "回测任务已提交",
                "task_id": task.id
            })
            
            logger.info(f"✅ 流式回测任务已提交: {task.id}")

        except Exception as e:
            logger.error(f"❌ 流式回测启动失败: {e}", exc_info=True)
            emit('backtest_error', {"message": str(e)})
    
    @socketio_instance.on('cancel_streaming_backtest')
    def handle_cancel_backtest(data=None):
        """【异步化改造】处理取消回测请求"""
        sid = request.sid
        
        if sid in active_backtests:
            task_id = active_backtests[sid]
            
            # 取消 Celery 任务
            success = cancel_backtest_task(task_id)
            
            if success:
                emit('backtest_cancel_ack', {"message": "正在停止回测..."})
                logger.info(f"收到取消回测请求，已取消任务 {task_id} (sid: {sid})")
            else:
                emit('backtest_cancel_ack', {"message": "取消任务失败"})
            
            # 清理记录
            del active_backtests[sid]
            
            # 取消订阅
            channel = f"backtest:{sid}"
            pubsub_manager.unsubscribe(channel, sid)
        else:
            emit('backtest_cancel_ack', {"message": "当前没有正在运行的回测"})
            logger.warning(f"收到取消回测请求，但当前没有运行的回测 (sid: {sid})")
    
    @socketio_instance.on('request_kline')
    def handle_request_kline(data):
        """请求 K 线数据（保持同步，因为数据查询很快）"""
        # 延迟导入
        from server.app import get_api
        
        symbol_code = data.get('symbol_code')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not symbol_code:
            emit('kline_data', {"error": "缺少 symbol_code"}, to=request.sid)
            return

        logger.debug(f"📈 请求 K 线 {symbol_code} | {start_date} ~ {end_date}")
        
        try:
            api_instance = get_api()
            history = api_instance.get_symbol_kline(symbol_code, start_date, end_date)
            emit('kline_data', {
                "request_id": data.get('request_id'),
                "symbol_code": symbol_code,
                "data": history
            }, to=request.sid)
        except Exception as e:
            logger.error(f"获取 K 线数据失败: {e}")
            emit('kline_data', {"error": str(e)}, to=request.sid)
    
    @socketio_instance.on('stop_optimization')
    def handle_stop_optimization(data):
        """【异步化改造】处理停止优化请求"""
        request_sid = request.sid
        target_sid = None
        
        try:
            if isinstance(data, dict):
                target_sid = data.get("sid") or data.get("session_id")
        except Exception:
            pass
        
        if not target_sid:
            target_sid = request_sid

        if target_sid in active_optimizations:
            task_id = active_optimizations[target_sid]
            
            # 取消 Celery 任务
            success = cancel_backtest_task(task_id)
            
            if success:
                emit('optimization_cancel_ack', {"message": "正在停止优化..."})
                logger.info(f"收到取消优化请求，已取消任务 {task_id} (sid: {target_sid})")
            else:
                emit('optimization_cancel_ack', {"message": "取消优化失败"})
            
            del active_optimizations[target_sid]
            
            # 取消订阅
            channel = f"optimization:{target_sid}"
            pubsub_manager.unsubscribe(channel, request_sid)
        else:
            emit('optimization_cancel_ack', {"message": "当前没有正在运行的优化"})
            logger.warning(f"收到取消优化请求，但当前没有运行的优化 (sid: {target_sid})")
    
    @socketio_instance.on('run_optimization')
    def handle_run_optimization(data):
        """【异步化改造】处理参数优化请求"""
        try:
            sid = request.sid
            channel = f"optimization:{sid}"
            
            # 检查是否是新格式
            if 'optimization_engine' in data and 'search_space' in data:
                # 新格式处理
                strategy_name = data.get('strategy_name')
                optimization_engine = data.get('optimization_engine', {})
                search_space = data.get('search_space', [])
                objective = data.get('objective', {})
                backtest = data.get('backtest', {})
                validation = data.get('validation', {})

                mode = data.get('mode') or validation.get('mode') or 'robust'
                
                method = optimization_engine.get('method', 'ga')
                if method == 'cmaes':
                    method = 'cma_es'
                algo_params = optimization_engine.get('params', {})
                
                start_date = backtest.get('start_date') or data.get('start_date')
                end_date = backtest.get('end_date') or data.get('end_date')
                
                if not all([strategy_name, start_date, end_date]):
                    emit('optimization_error', {"message": "缺少必要参数: strategy_name, start_date, end_date"})
                    return
                
                logger.info(f"🔍 [Async] 收到参数优化请求: {strategy_name} | {start_date}~{end_date} | method: {method}")
                
                # 构建 param_ranges
                param_ranges = []
                for param_spec in search_space:
                    param_name = param_spec.get('name')
                    param_type = param_spec.get('type', 'float')
                    param_min = param_spec.get('min')
                    param_max = param_spec.get('max')
                    
                    if not all([param_name, param_min is not None, param_max is not None]):
                        logger.warning(f"跳过无效参数: {param_spec}")
                        continue
                    
                    lower, upper = float(param_min), float(param_max)
                    
                    if lower >= upper:
                        logger.warning(f"参数范围验证失败: {param_name}")
                        lower, upper = min(lower, upper - 1), max(upper, lower + 1)
                    
                    param_range = {
                        "name": param_name,
                        "bounds": [lower, upper],
                        "type": param_type
                    }
                    
                    if method == 'grid' and 'step' in param_spec:
                        param_range['step'] = float(param_spec['step'])
                    
                    param_ranges.append(param_range)
                
                if not param_ranges:
                    emit('optimization_error', {"message": "没有有效的参数范围定义"})
                    return
                
                target_metric = objective.get('target', 'sharpe_ratio')
                metric_mapping = {
                    'sharpe_ratio': 'sharpe_ratio',
                    'total_return': 'total_return',
                    'max_drawdown': 'max_drawdown',
                    'win_rate': 'win_rate',
                    'calmar_ratio': 'calmar_ratio'
                }
                target_metric = metric_mapping.get(target_metric, 'sharpe_ratio')
                
                # 订阅频道
                pubsub_manager.subscribe(channel, sid)
                
                # 提交 Celery 任务
                task = run_optimization_task.delay(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    param_ranges=param_ranges,
                    method=method,
                    algo_params=algo_params,
                    target_metric=target_metric,
                    mode=mode,
                    sid=sid
                )
                
                active_optimizations[sid] = task.id
                
                emit('optimization_started', {
                    "message": "优化任务已启动",
                    "task_id": task.id
                })
                
                logger.info(f"✅ 优化任务已提交: {task.id}")
                
            else:
                # 旧格式处理
                strategy_name = data.get('strategy_name')
                param_ranges = data.get('param_ranges', [])
                start_date = data.get('start_date')
                end_date = data.get('end_date')
                method = data.get('method', 'ga')
                algo_params = data.get('algo_params', {})
                target_metric = data.get('target_metric', 'sharpe_ratio')
                
                if not all([strategy_name, start_date, end_date, param_ranges]):
                    emit('optimization_error', {"message": "缺少必要参数"})
                    return
                
                logger.info(f"🔍 [Async] 收到参数优化请求（旧格式）: {strategy_name}")
                
                # 订阅频道
                pubsub_manager.subscribe(channel, sid)
                
                # 提交 Celery 任务
                task = run_optimization_task.delay(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    param_ranges=param_ranges,
                    method=method,
                    algo_params=algo_params,
                    target_metric=target_metric,
                    mode='robust',
                    sid=sid
                )
                
                active_optimizations[sid] = task.id
                
                emit('optimization_started', {
                    "message": "优化任务已启动",
                    "task_id": task.id
                })
                
        except Exception as e:
            logger.error(f"处理优化请求失败: {e}", exc_info=True)
            emit('optimization_error', {"message": str(e)})
