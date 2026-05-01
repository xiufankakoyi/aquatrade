"""
基础配置加载模块 (config/setting.py)
从 secrets.py 或环境变量加载配置信息。

【配置优先级】
==============
1. secrets.py（推荐，更安全）
2. 环境变量（兼容旧方式）

【安全说明】
============
- 敏感信息（API密钥、Token）统一存放在 config/secrets.py
- secrets.py 已在 .gitignore 中，不会被提交到 Git
- 首次使用请复制 secrets_template.py 为 secrets.py 并填入真实值
"""
import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_secrets = None

def _get_secrets():
    """
    获取 Secrets 配置实例
    
    Returns:
        Secrets 类或 None
    """
    global _secrets
    if _secrets is not None:
        return _secrets
    
    try:
        from config.secrets import Secrets
        _secrets = Secrets
        return _secrets
    except ImportError:
        return None


def _get_config(key: str, env_default: str = '') -> str:
    """
    统一获取配置值
    
    优先级：secrets.py > 环境变量 > 默认值
    
    Args:
        key: 配置键名
        env_default: 环境变量默认值
        
    Returns:
        配置值
    """
    secrets = _get_secrets()
    if secrets:
        value = getattr(secrets, key, None)
        if value:
            return value
    
    return os.getenv(key, env_default)


class Setting:
    """配置类 - 统一管理所有配置项"""
    
    # ============================================
    # 核心 Token & API Key（敏感配置）
    # ============================================
    TUSHARE_TOKEN = _get_config('TUSHARE_TOKEN')
    
    # DragonEye 凭证
    DRAGON_USERNAME = _get_config('DRAGON_USERNAME')
    DRAGON_PASSWORD = _get_config('DRAGON_PASSWORD')
    DRAGON_TOKEN = _get_config('DRAGON_TOKEN')
    
    # QuickTiny (stock.quicktiny.cn) 爬虫凭证
    QUICKTINY_TOKEN = _get_config('QUICKTINY_TOKEN')
    QUICKTINY_USERNAME = _get_config('QUICKTINY_USERNAME')
    QUICKTINY_PASSWORD = _get_config('QUICKTINY_PASSWORD')
    
    # 飞书配置
    FEISHU_WEBHOOK = _get_config('FEISHU_WEBHOOK')
    FEISHU_APP_ID = _get_config('FEISHU_APP_ID')
    FEISHU_APP_SECRET = _get_config('FEISHU_APP_SECRET')
    
    # LLM 配置
    LLM_API_BASE = _get_config('LLM_API_BASE', 'http://127.0.0.1:1234/v1')
    LLM_API_KEY = _get_config('LLM_API_KEY', 'lm-studio')
    LLM_MODEL_NAME = _get_config('LLM_MODEL_NAME', 'qwen2.5-7b')
    
    # ============================================
    # 数据库后端配置（非敏感）
    # ============================================
    DB_BACKEND = os.getenv('DB_BACKEND', 'lancedb')
    DB_PATH = os.getenv('DB_PATH', '')
    
    # LanceDB 配置
    LANCEDB_PATH = os.getenv('LANCEDB_PATH', '')
    
    # Apache Arrow 交互层配置
    ARROW_BATCH_SIZE = int(os.getenv('ARROW_BATCH_SIZE', '10000'))
    ARROW_ZERO_COPY = os.getenv('ARROW_ZERO_COPY', 'true').lower() == 'true'
    
    # GPU 加速配置
    USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'
    
    # ============================================
    # 策略与行情阈值（非敏感）
    # ============================================
    MIN_MARKET_CAP = float(os.getenv('MIN_MARKET_CAP', '20000'))
    MAX_MARKET_CAP = float(os.getenv('MAX_MARKET_CAP', '5000000'))
    MIN_PRICE = float(os.getenv('MIN_PRICE', '5.0'))
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '1000000'))
    
    # ============================================
    # 检查配置完整性
    # ============================================
    @classmethod
    def check_secrets_configured(cls) -> bool:
        """
        检查 secrets.py 是否已配置
        
        Returns:
            bool: 是否存在 secrets.py
        """
        secrets_path = Path(__file__).parent / 'secrets.py'
        return secrets_path.exists()
    
    @classmethod
    def validate_required_keys(cls) -> list[str]:
        """
        验证必需的密钥是否已配置
        
        Returns:
            list: 缺失的配置项列表
        """
        required_keys = ['TUSHARE_TOKEN']
        missing = []
        
        for key in required_keys:
            if not getattr(cls, key, None):
                missing.append(key)
        
        return missing


if not Setting.check_secrets_configured():
    warnings.warn(
        "config/secrets.py 不存在，请复制 secrets_template.py 为 secrets.py 并填入配置。"
        "\n当前将尝试从环境变量读取配置。",
        UserWarning
    )
