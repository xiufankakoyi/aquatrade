# core/dragon_eye/manager.py
import os
import pandas as pd
import polars as pl
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from data_svc.lance_manager import LanceDBManager
from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)

class DragonEyeManager:
    """DragonEye 模块数据管理器，专注于龙头股与市场情绪数据的持久化"""
    
    def __init__(self):
        # 使用统一的数据目录
        self.parquet_dir = Path(Config.PARQUET_DIR)
        self.lance_dir = self.parquet_dir / "lance_db"
        
        # 初始化两个核心表管理器
        self.stock_mgr = LanceDBManager(table_name="dragon_stock")
        self.sentiment_mgr = LanceDBManager(table_name="market_sentiment")

    def upsert_stocks(self, df_stocks: pd.DataFrame):
        """更新龙头个股数据"""
        if df_stocks.empty:
            return
            
        logger.info(f"Upserting {len(df_stocks)} records into dragon_stock")
        
        # 补全 _id 字段用于 Upsert
        if "_id" not in df_stocks.columns:
            df_stocks["_id"] = df_stocks["stock_code"].astype(str) + "_" + df_stocks["trade_date"].astype(str)
            
        self.stock_mgr.upsert_daily_data(df_stocks)

    def upsert_sentiment(self, df_sentiment: pd.DataFrame):
        """更新当日市场情绪大盘指标"""
        if df_sentiment.empty:
            return
            
        logger.info(f"Upserting sentiment record for {df_sentiment['trade_date'].iloc[0]}")
        
        # 补全 _id
        if "_id" not in df_sentiment.columns:
            df_sentiment["_id"] = df_sentiment["trade_date"].astype(str)
            
        self.sentiment_mgr.upsert_daily_data(df_sentiment)

    def get_historical_dragon(self, start_date: str, end_date: str) -> pl.DataFrame:
        """获取历史龙头股列表"""
        return self.stock_mgr.load_to_polars(start_date=start_date, end_date=end_date)

    def get_market_sentiment(self, start_date: str, end_date: str) -> pl.DataFrame:
        """获取历史大盘情绪指标"""
        return self.sentiment_mgr.load_to_polars(start_date=start_date, end_date=end_date)
