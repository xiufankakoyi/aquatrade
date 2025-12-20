"""
配置文件
"""
import os

class Config:
    """配置类"""
    # 数据库路径
    DB_PATH = os.getenv('DB_PATH', 'database/stock_data.db')
    
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
    BOARD_LOT = 100  # 每手股数
    
    # GPU 加速配置
    USE_GPU_ACCELERATION = os.getenv('USE_GPU', 'false').lower() == 'true'
