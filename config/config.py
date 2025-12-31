"""
配置文件
"""
import os

class Config:
    """配置类"""
    # 1. 获取项目根目录
    # config/config.py -> config/ -> AquaTrade/
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 2. 数据库路径：基于项目根目录动态生成
    # 优先使用环境变量，否则使用默认路径
    DB_PATH = os.environ.get('DB_PATH') or os.path.join(
        BASE_DIR, 'data_svc', 'database', 'stock_data.db'
    )
    
    # 3. Parquet 数据目录
    PARQUET_DIR = os.path.join(BASE_DIR, 'parquet_data')
    
    # 4. 爬虫数据目录
    SPIDER_DATA_DIR = os.path.join(BASE_DIR, 'data_svc', 'spider', 'data')
    
    # 股票过滤配置
    EXCLUDE_ST = True  # 排除 ST 股票
    EXCLUDE_KC = True  # 排除科创板
    EXCLUDE_CY = True  # 排除创业板
    
    # 市值过滤
    MIN_MARKET_CAP = 20_000  # 最小市值（万元）
    MAX_MARKET_CAP = 5_000_000  # 最大市值（万元）
    
    # 价格过滤
    MIN_PRICE = 5.0  # 最小价格
    
    # 交易配置
    INITIAL_CAPITAL = 1_000_000  # 初始资金（元）
    COMMISSION_RATE = 0.0005  # CHANGED: 佣金费率（万分之五）
    MIN_COMMISSION = 5.0  # CHANGED: 最低手续费（元）
    SELL_TAX = 0.001  # CHANGED: 卖出印花税（千分之一，0.1%）
    BOARD_LOT = 100  # 每手股数
    
    # GPU 加速配置
    USE_GPU_ACCELERATION = os.getenv('USE_GPU', 'false').lower() == 'true'
    
    # Redis 配置（用于异步任务队列和消息传递）
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_TASK_QUEUE = os.getenv('REDIS_TASK_QUEUE', 'aqua_tasks')
    REDIS_NOTIFICATION_CHANNEL_PREFIX = os.getenv('REDIS_NOTIFICATION_CHANNEL_PREFIX', 'aqua_notifications')
    
    # Optuna Redis Storage 配置
    OPTUNA_REDIS_STORAGE_URL = os.getenv('OPTUNA_REDIS_STORAGE_URL', 'redis://localhost:6379/0')