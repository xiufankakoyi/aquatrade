"""
Celery Worker 启动入口
=====================

【功能说明】
本模块是 Celery Worker 的启动入口，用于启动独立的工作进程执行异步任务。

【启动方式】
1. 确保 Redis 运行:
   docker run -d -p 6379:6379 redis:alpine

2. 启动 Worker:
   celery -A worker worker --loglevel=info --concurrency=4

3. 启动 Flower (监控界面，可选):
   celery -A worker flower --port=5555

【参数说明】
- --concurrency: Worker 并发数（建议设置为 CPU 核心数）
- --loglevel: 日志级别 (debug/info/warning/error)
- --queues: 指定队列（默认处理所有队列）
  例: celery -A worker worker -Q backtest,optimization

【环境变量】
- REDIS_URL: Redis 连接地址 (默认: redis://localhost:6379/0)
- CELERY_WORKER_CONCURRENCY: Worker 并发数
- LOG_LEVEL: 日志级别
"""
import os
import sys

# 添加项目根目录到 Python 路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 导入 Celery 应用实例
from config.celery_config import celery_app
from config.logger import get_logger

logger = get_logger(__name__)


def setup_worker():
    """
    Worker 启动前的初始化
    
    可以在这里执行：
    - 数据库连接预热
    - 缓存预热
    - 日志配置
    """
    logger.info("=" * 60)
    logger.info("AquaTrade Celery Worker 启动中...")
    logger.info("=" * 60)
    
    # 打印配置信息
    broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    concurrency = os.getenv('CELERY_WORKER_CONCURRENCY', '4')
    
    logger.info(f"Broker: {broker_url}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")
    
    # 预热数据连接（可选）
    try:
        from config.config import Config
        logger.info(f"Database: {Config.DB_PATH}")
        logger.info(f"Backend: {Config.get_data_interface()}")
    except Exception as e:
        logger.warning(f"配置加载警告: {e}")
    
    logger.info("=" * 60)


# Worker 连接事件
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """配置周期性任务（如果需要）"""
    # 示例: 每小时清理一次过期任务
    # sender.add_periodic_task(3600.0, cleanup_old_tasks.s(), name='cleanup every hour')
    pass


@celery_app.on_after_finalize.connect
def on_worker_ready(sender, **kwargs):
    """Worker 准备就绪后的回调"""
    logger.info("Worker 已准备就绪，开始处理任务")


# 启动初始化
setup_worker()


# 导出 Celery 应用（这是 celery 命令需要的）
if __name__ == '__main__':
    # 直接运行此文件时的处理
    import argparse
    
    parser = argparse.ArgumentParser(description='AquaTrade Celery Worker')
    parser.add_argument('--concurrency', type=int, default=4, help='Worker 并发数')
    parser.add_argument('--loglevel', type=str, default='info', help='日志级别')
    
    args = parser.parse_args()
    
    # 使用 celery 命令启动
    import subprocess
    
    cmd = [
        'celery',
        '-A', 'worker',
        'worker',
        '--concurrency', str(args.concurrency),
        '--loglevel', args.loglevel
    ]
    
    logger.info(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd)
