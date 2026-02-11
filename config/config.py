"""
配置文件 (config/config.py)
聚合 Setting 模块与动态生成的路径配置。
"""
import os
from pathlib import Path
from config.setting import Setting

class Config:
    """配置类 - 统一引用 Setting 模块"""
    # 1. 基础路径配置
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 2. 数据库配置
    # 优先使用环境变量路径，否则使用默认
    DB_PATH = Setting.DB_PATH or os.path.join(
        BASE_DIR, 'data', 'database', 'stock_data.db'
    )
    DB_BACKEND = Setting.DB_BACKEND
    
    # 3. 核心目录
    PARQUET_DIR = os.path.join(BASE_DIR, 'data', 'parquet_data')
    SPIDER_DATA_DIR = os.path.join(BASE_DIR, 'data', 'spider_data')
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    MODELS_DIR = os.path.join(BASE_DIR, 'models')
    
    # 4. 核心 Token & API Key (从 Setting 读取)
    TUSHARE_TOKEN = Setting.TUSHARE_TOKEN
    DRAGON_USERNAME = Setting.DRAGON_USERNAME
    DRAGON_PASSWORD = Setting.DRAGON_PASSWORD
    DRAGON_TOKEN = Setting.DRAGON_TOKEN
    FEISHU_WEBHOOK = Setting.FEISHU_WEBHOOK
    
    # LLM 配置
    LLM_API_BASE = Setting.LLM_API_BASE
    LLM_API_KEY = Setting.LLM_API_KEY
    LLM_MODEL_NAME = Setting.LLM_MODEL_NAME
    LLM_TEMPERATURE = 0.1
    LLM_MAX_TOKENS = 4096
    
    # 5. 策略行情阈值
    MIN_MARKET_CAP = Setting.MIN_MARKET_CAP
    MAX_MARKET_CAP = Setting.MAX_MARKET_CAP
    MIN_PRICE = Setting.MIN_PRICE
    INITIAL_CAPITAL = Setting.INITIAL_CAPITAL
    
    # 过滤开关
    EXCLUDE_ST = True
    EXCLUDE_KC = True
    EXCLUDE_CY = True
    
    # 交易细则
    COMMISSION_RATE = 0.0005
    MIN_COMMISSION = 5.0
    SELL_TAX = 0.001
    BOARD_LOT = 100
    
    # 6. 环境/中间件配置
    USE_GPU_ACCELERATION = Setting.USE_GPU
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_TASK_QUEUE = os.getenv('REDIS_TASK_QUEUE', 'aqua_tasks')
    REDIS_NOTIFICATION_CHANNEL_PREFIX = os.getenv('REDIS_NOTIFICATION_CHANNEL_PREFIX', 'aqua_notifications')
    OPTUNA_REDIS_STORAGE_URL = os.getenv('OPTUNA_REDIS_STORAGE_URL', 'redis://localhost:6379/0')