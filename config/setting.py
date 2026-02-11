"""
基础配置加载模块 (config/setting.py)
从环境变量或 .env 文件中加载原始配置信息，避免硬编码。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Setting:
    # --- 核心 Token & API Key ---
    TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN', '')
    
    # DragonEye 凭证
    DRAGON_USERNAME = os.getenv('DRAGON_USERNAME', '')
    DRAGON_PASSWORD = os.getenv('DRAGON_PASSWORD', '')
    DRAGON_TOKEN = os.getenv('DRAGON_TOKEN', '')
    FEISHU_WEBHOOK = os.getenv('FEISHU_WEBHOOK', '')

    # LLM 配置
    LLM_API_BASE = os.getenv('LLM_API_BASE', 'http://127.0.0.1:1234/v1')
    LLM_API_KEY = os.getenv('LLM_API_KEY', 'lm-studio')
    LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'qwen2.5-7b')
    
    # --- 系统路径与存储 ---
    DB_BACKEND = os.getenv('DB_BACKEND', 'duckdb')
    DB_PATH = os.getenv('DB_PATH', '') # 为空则由 config.py 动态生成默认路径
    USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'
    
    # --- 策略与行情阈值 (Thresholds) ---
    MIN_MARKET_CAP = float(os.getenv('MIN_MARKET_CAP', '20000'))
    MAX_MARKET_CAP = float(os.getenv('MAX_MARKET_CAP', '5000000'))
    MIN_PRICE = float(os.getenv('MIN_PRICE', '5.0'))
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '1000000'))
