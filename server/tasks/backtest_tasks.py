"""
回测任务定义
===========

【功能说明】
定义 Celery 异步任务，用于在独立 Worker 进程中执行回测计算。

【任务列表】
1. run_backtest_task: 非流式回测任务
2. run_streaming_backtest_task: 流式回测任务（支持实时进度推送）
3. run_optimization_task: 参数优化任务

【使用方式】
```python
from server.tasks.backtest_tasks import run_backtest_task

# 提交任务
task = run_backtest_task.delay(
    strategy_name='MyStrategy',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# 获取任务ID
task_id = task.id
```
"""
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from config.celery_config import TaskStatus, TaskProgressUpdater, celery_app
from config.config import Config
from config.logger import get_logger
from server.services.task_status_service import get_task_status_service, TaskState

logger = get_logger(__name__)


# ============================================================================
# 辅助函数
# ============================================================================

def _get_redis_client():
    """获取 Redis 客户端"""
    try:
        import redis
        return redis.from_url(Config.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}")
        return None


def _publish_progress(task_id: str, channel: str, data: Dict[str, Any]):
    """发布进度到 Redis 频道"""
    redis_client = _get_redis_client()
    if redis_client:
        try:
            redis_client.publish(channel, json.dumps({
                'task_id': task_id,
                'timestamp': time.time(),
                **data
            }))
        except Exception as e:
            logger.warning(f"进度发布失败: {e}")


# ============================================================================
# 任务定义
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_backtest_task(
    self,
    strategy_name: str,
    start_date: str,
    end_date: str,
    params: Optional[Dict[str, Any]] = None,
    profile_id: Optional[int] = None,
    use_lancedb: bool = False
) -> Dict[str, Any]:
    """
    非流式回测任务
    
    在 Worker 进程中执行完整回测，返回最终结果。
    适用于 HTTP API 异步调用场景。
    
    Args:
        strategy_name: 策略名称
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        params: 策略参数
        profile_id: 参数预设ID
        use_lancedb: 是否使用 LanceDB 后端
        
    Returns:
        Dict: 回测结果
    """
    task_id = self.request.id
    task_service = get_task_status_service()
    
    # 注册任务
    task_service.register_task(task_id, 'backtest', {
        'strategy_name': strategy_name,
        'start_date': start_date,
        'end_date': end_date,
    })
    
    logger.info(f"[Task {task_id}] 开始回测: {strategy_name} ({start_date} ~ {end_date})")
    
    try:
        # 更新状态为开始
        task_service.update_task_state(task_id, TaskState.STARTED)
        task_service.update_progress(task_id, 10, 100, "初始化回测环境...")
        
        # 处理 profile 参数
        effective_params = params or {}
        if profile_id is not None:
            try:
                from core.profiles.profile_repository import get_profile as load_profile
                profile = load_profile(int(profile_id))
                if profile:
                    params_from_profile = profile.get("params") or {}
                    if isinstance(params_from_profile, dict):
                        effective_params = {**params_from_profile, **effective_params}
            except Exception as e:
                logger.warning(f"加载 Profile 失败: {e}")
        
        task_service.update_progress(task_id, 30, 100, "加载数据和策略...")
        
        # 执行回测
        from server.app import get_api
        api = get_api()
        
        task_service.update_progress(task_id, 50, 100, "运行回测计算...")
        
        result = api.run_backtest_and_get_data(
            strategy_name,
            start_date,
            end_date,
            params=effective_params,
        )
        
        # 检查结果
        if isinstance(result, dict) and 'error' in result:
            raise Exception(result['error'])
        
        task_service.update_progress(task_id, 90, 100, "处理结果...")
        
        # 存储结果
        task_service.store_result(task_id, result)
        
        # 更新状态为完成
        task_service.update_task_state(
            task_id, 
            TaskState.SUCCESS,
            result={'summary': {
                'strategy_name': strategy_name,
                'total_return': result.get('metrics', {}).get('totalReturn'),
                'sharpe_ratio': result.get('metrics', {}).get('sharpeRatio'),
            }}
        )
        
        logger.info(f"[Task {task_id}] 回测完成: {strategy_name}")
        
        return result
        
    except SoftTimeLimitExceeded:
        error_msg = "回测任务超时"
        logger.error(f"[Task {task_id}] {error_msg}")
        task_service.update_task_state(task_id, TaskState.TIMEOUT, error=error_msg)
        raise
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Task {task_id}] 回测失败: {error_msg}", exc_info=True)
        task_service.update_task_state(task_id, TaskState.FAILURE, error=error_msg)
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"[Task {task_id}] 将在 {self.default_retry_delay} 秒后重试")
            raise self.retry(exc=e)
        
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def run_streaming_backtest_task(
    self,
    strategy_name: str,
    start_date: str,
    end_date: str,
    sid: str,
    benchmark_code: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    backtest_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    流式回测任务
    
    在 Worker 进程中执行流式回测，通过 Redis Pub/Sub 实时推送进度。
    适用于 SocketIO 实时推送场景。
    
    Args:
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        sid: SocketIO 会话ID（用于构建频道名）
        benchmark_code: 基准代码
        params: 策略参数
        backtest_config: 回测配置
        
    Returns:
        Dict: 最终回测结果
    """
    task_id = self.request.id
    channel = f"backtest:{sid}"
    
    task_service = get_task_status_service()
    task_service.register_task(task_id, 'streaming_backtest', {
        'strategy_name': strategy_name,
        'sid': sid,
    })
    
    logger.info(f"[Task {task_id}] 开始流式回测: {strategy_name} (sid: {sid})")
    
    # 发布开始事件
    _publish_progress(task_id, channel, {
        'type': 'backtest_start',
        'data': {'message': '回测任务已开始', 'task_id': task_id}
    })
    
    try:
        from server.app import get_api
        api = get_api()
        
        # 收集完整结果
        final_result = {}
        equity_records = []
        trades = []
        
        # 执行流式回测
        for update in api.stream_backtest(
            strategy_name,
            start_date,
            end_date,
            benchmark_code,
            params=params,
            backtest_config=backtest_config,
        ):
            update_type = update.get('type')
            data = update.get('data', {})
            
            # 转发事件到 Redis 频道
            _publish_progress(task_id, channel, {
                'type': update_type,
                'data': data
            })
            
            # 收集数据用于最终返回
            if update_type == 'daily_equity':
                equity_records.append({
                    'date': data.get('date'),
                    'total_value': data.get('strategyReturn')
                })
            elif update_type == 'new_trade':
                trades.append(data)
            elif update_type == 'final_metrics':
                final_result['metrics'] = data
            elif update_type == 'stream_complete':
                final_result['completed'] = True
            elif update_type == 'error':
                raise Exception(data.get('message', '回测发生错误'))
        
        # 构建完整结果
        result = {
            'task_id': task_id,
            'strategy_name': strategy_name,
            'start_date': start_date,
            'end_date': end_date,
            'equity_records_count': len(equity_records),
            'trades_count': len(trades),
            'final_result': final_result,
            'completed_at': datetime.now().isoformat(),
        }
        
        # 发布完成事件
        _publish_progress(task_id, channel, {
            'type': 'task_complete',
            'data': result
        })
        
        task_service.update_task_state(task_id, TaskState.SUCCESS, result=result)
        
        logger.info(f"[Task {task_id}] 流式回测完成")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Task {task_id}] 流式回测失败: {error_msg}", exc_info=True)
        
        # 发布错误事件
        _publish_progress(task_id, channel, {
            'type': 'backtest_error',
            'data': {'message': error_msg}
        })
        
        task_service.update_task_state(task_id, TaskState.FAILURE, error=error_msg)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=60, time_limit=3600*2)
def run_optimization_task(
    self,
    strategy_name: str,
    start_date: str,
    end_date: str,
    param_ranges: list,
    method: str = 'ga',
    algo_params: Optional[Dict] = None,
    target_metric: str = 'sharpe_ratio',
    mode: str = 'robust',
    sid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    参数优化任务
    
    在 Worker 进程中执行参数优化，支持长时间运行的优化算法。
    
    Args:
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        param_ranges: 参数范围列表
        method: 优化算法 (ga/cma_es/grid)
        algo_params: 算法参数
        target_metric: 目标指标
        mode: 优化模式
        sid: SocketIO 会话ID（可选，用于推送进度）
        
    Returns:
        Dict: 优化结果
    """
    task_id = self.request.id
    channel = f"optimization:{sid}" if sid else None
    
    task_service = get_task_status_service()
    task_service.register_task(task_id, 'optimization', {
        'strategy_name': strategy_name,
        'method': method,
    })
    
    logger.info(f"[Task {task_id}] 开始参数优化: {strategy_name} (method: {method})")
    
    if channel:
        _publish_progress(task_id, channel, {
            'type': 'optimization_started',
            'data': {'message': '优化任务已启动'}
        })
    
    try:
        from core.optimization.optimization_engine import OptimizationEngine
        
        engine = OptimizationEngine()
        
        # 创建进度回调
        def progress_callback(iteration: int, total: int, best_score: float, params: dict):
            task_service.update_progress(
                task_id, 
                iteration, 
                total, 
                f"优化迭代中... 最佳得分: {best_score:.4f}",
                best_score=best_score,
                current_params=params
            )
            
            if channel:
                _publish_progress(task_id, channel, {
                    'type': 'optimization_progress',
                    'data': {
                        'iteration': iteration,
                        'total': total,
                        'percent': int((iteration / total) * 100),
                        'best_score': best_score,
                        'params': params
                    }
                })
        
        # 执行优化
        result = engine.run_optimization(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            param_ranges=param_ranges,
            method=method,
            algo_params=algo_params or {},
            target_metric=target_metric,
            mode=mode,
            progress_callback=progress_callback,
        )
        
        # 存储结果
        task_service.store_result(task_id, result)
        task_service.update_task_state(task_id, TaskState.SUCCESS, result=result)
        
        if channel:
            _publish_progress(task_id, channel, {
                'type': 'optimization_complete',
                'data': result
            })
        
        logger.info(f"[Task {task_id}] 参数优化完成")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Task {task_id}] 参数优化失败: {error_msg}", exc_info=True)
        
        if channel:
            _publish_progress(task_id, channel, {
                'type': 'optimization_error',
                'data': {'message': error_msg}
            })
        
        task_service.update_task_state(task_id, TaskState.FAILURE, error=error_msg)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        raise


# ============================================================================
# 任务管理工具函数
# ============================================================================

def get_backtest_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取回测任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 任务状态信息
    """
    from config.celery_config import get_task_status
    return get_task_status(task_id)


def cancel_backtest_task(task_id: str) -> bool:
    """
    取消回测任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        bool: 是否成功取消
    """
    from config.celery_config import revoke_task
    
    # 更新本地状态
    task_service = get_task_status_service()
    task_service.update_task_state(task_id, TaskState.CANCELLED)
    
    # 取消 Celery 任务
    return revoke_task(task_id)
