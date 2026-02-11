# core/dragon_eye/service.py
import subprocess
import sys
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from config.config import Config
from config.logger import get_logger
from core.dragon_eye.manager import DragonEyeManager
from data_svc.spiders.dragon_spider.cleaner import StockDataCleaner

logger = get_logger(__name__)

class DragonEyeService:
    """DragonEye 模块核心服务：编排爬虫、清洗、入库与推送"""
    
    def __init__(self):
        self.manager = DragonEyeManager()
        self.project_root = Path(Config.BASE_DIR)
        self.spider_path = self.project_root / "data_svc" / "spiders" / "dragon_spider" / "main.py"
        self.data_lake_dir = self.project_root / "data" / "spider_data" / "dragon_eye" / "data_lake"

    def run_crawler(self, target_date: Optional[str] = None):
        """启动 Selenium 爬虫抓取数据"""
        cmd = [sys.executable, str(self.spider_path)]
        if target_date:
            cmd.extend(["--date", target_date])
            
        logger.info(f"Starting DragonEye spider: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Spider finished successfully")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Spider failed: {e.stderr}")
            return False, e.stderr

    def process_and_persist(self, target_date: str):
        """清洗抓取到的 JSON 数据并保存到 LanceDB"""
        date_dir = self.data_lake_dir / target_date
        if not date_dir.exists():
            logger.error(f"Data directory not found for date: {target_date}")
            return False, "Data directory missing"

        try:
            cleaner = StockDataCleaner(str(date_dir))
            
            # 1. 生成并入库大盘情绪
            sentiment_summary = cleaner.generate_market_dashboard()
            if sentiment_summary:
                df_sent = pd.DataFrame([sentiment_summary])
                self.manager.upsert_sentiment(df_sent)
                
            # 2. 生成并入库龙头个股
            stock_matrix = cleaner.generate_stock_feature_matrix()
            if stock_matrix:
                df_stocks = pd.DataFrame(stock_matrix)
                self.manager.upsert_stocks(df_stocks)
                
            # 3. 生成 AI 简报文件
            cleaner.generate_ai_daily_brief()
            
            logger.info(f"Process and persist completed for {target_date}")
            return True, "Success"
        except Exception as e:
            logger.error(f"Failed to process data: {e}")
            return False, str(e)

    def get_latest_brief(self, target_date: str) -> str:
        """获取最新的 AI 简报内容"""
        brief_path = self.data_lake_dir / target_date / "ai_daily_brief.txt"
        if brief_path.exists():
            return brief_path.read_text(encoding='utf-8')
        return ""

    def send_to_feishu(self, target_date: str):
        """触发飞书推送 (复用 core/dragon_eye/combined.py 中的逻辑)"""
        # 这里后续可以重构 combined.py 中的 FeishuPush 类
        from core.dragon_eye.combined import FeishuPush
        
        # 飞书 Webhook 建议从环境变量或配置读取
        webhook_url = getattr(Config, 'FEISHU_WEBHOOK', "") 
        if not webhook_url:
            return False, "Feishu Webhook not configured"
            
        brief_content = self.get_latest_brief(target_date)
        if not brief_content:
            return False, "Brief content is empty"
            
        pusher = FeishuPush(webhook_url)
        markdown = pusher.txt_to_markdown(brief_content)
        success = pusher.push_markdown(markdown)
        return success, "Pushed to Feishu" if success else "Failed to push"
