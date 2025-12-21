"""
Worker Process: Redis Consumer

监听 Redis List (aqua_tasks)，取出任务并执行回测/优化。
将进度/日志通过 RedisSocketIOPublisher 发布到 Redis Channel。
"""
import os
import sys
import json
import time
import signal
import traceback
from typing import Dict, Any, Optional
import redis

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import get_logger
from utils.redis_socketio_publisher import RedisSocketIOPublisher
from backtest.optimization_engine import StrategyOptimizer
from database.optimized_data_query import OptimizedStockDataQuery

logger = get_logger(__name__)

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TASK_QUEUE = "aqua_tasks"  # Redis List 名称
NOTIFICATION_CHANNEL_PREFIX = "aqua_notifications"

# 全局变量
running = True
redis_client = None
publisher = None


def signal_handler(signum, frame):
    """处理退出信号"""
    global running
    logger.info("收到退出信号，正在停止 Worker...")
    running = False


def init_redis():
    """初始化 Redis 连接"""
    global redis_client, publisher
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info(f"Redis 连接成功: {REDIS_URL}")
        
        publisher = RedisSocketIOPublisher(redis_url=REDIS_URL, channel_prefix=NOTIFICATION_CHANNEL_PREFIX)
        logger.info("RedisSocketIOPublisher 初始化成功")
    except Exception as e:
        logger.error(f"Redis 初始化失败: {e}")
        raise


def process_optimization_task(task_data: Dict[str, Any]):
    """
    处理优化任务
    
    Args:
        task_data: 任务数据，包含 sid, config 等
    """
    sid = task_data.get("sid")
    config = task_data.get("config", {})
    
    logger.info(f"开始处理优化任务 (sid: {sid})")
    
    try:
        # 初始化数据查询实例
        db_path = config.get("db_path") or os.getenv("DB_PATH", "database/stock_data.db")
        data_query = OptimizedStockDataQuery(db_path=db_path, warmup=True)
        
        # 创建优化器实例，传入 RedisSocketIOPublisher 替代 socketio
        optimizer = StrategyOptimizer(
            data_query=data_query,
            socketio=publisher,  # 使用 RedisSocketIOPublisher
            logger=logger,
            sid=sid,
            stop_event=None  # Worker 进程不需要 stop_event
        )
        
        # 运行优化
        logger.info(f"开始运行优化 (sid: {sid})")
        result = optimizer.run_optimization(config)
        
        logger.info(f"优化任务完成 (sid: {sid})")
        
        # 发布完成消息
        if publisher:
            publisher.emit_complete(result, sid=sid)
        
        return result
        
    except Exception as e:
        error_msg = f"优化任务失败 (sid: {sid}): {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc()
        
        # 发布错误消息
        if publisher:
            publisher.emit_error(str(e), sid=sid)
        
        raise


def main():
    """Worker 主循环"""
    global running, redis_client
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化 Redis
    try:
        init_redis()
    except Exception as e:
        logger.error(f"初始化失败，退出: {e}")
        sys.exit(1)
    
    logger.info(f"Worker 启动成功，监听队列: {TASK_QUEUE}")
    logger.info("按 Ctrl+C 停止 Worker")
    
    # 主循环：从 Redis List 中取出任务并处理
    while running:
        try:
            # 阻塞式取出任务（BRPOP: Blocking Right Pop）
            # 超时时间 1 秒，允许定期检查 running 标志
            result = redis_client.brpop(TASK_QUEUE, timeout=1)
            
            if result is None:
                # 超时，继续循环
                continue
            
            # result 格式: (list_name, task_json_string)
            _, task_json = result
            task_data = json.loads(task_json)
            
            logger.info(f"收到任务: {task_data.get('sid', 'unknown')}")
            
            # 处理任务
            try:
                process_optimization_task(task_data)
            except Exception as e:
                logger.error(f"处理任务失败: {e}", exc_info=True)
                # 继续处理下一个任务，不退出 Worker
            
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接错误: {e}")
            logger.info("尝试重新连接...")
            time.sleep(5)
            try:
                init_redis()
            except Exception:
                logger.error("重新连接失败，退出")
                break
        except KeyboardInterrupt:
            logger.info("收到键盘中断，退出")
            break
        except Exception as e:
            logger.error(f"Worker 主循环错误: {e}", exc_info=True)
            time.sleep(1)  # 避免快速循环
    
    # 清理资源
    logger.info("Worker 正在关闭...")
    if publisher:
        publisher.close()
    if redis_client:
        redis_client.close()
    logger.info("Worker 已关闭")


if __name__ == "__main__":
    main()

