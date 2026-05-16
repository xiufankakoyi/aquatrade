#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入 DragonEye 爬虫数据到 Parquet 存储"""

import json
import pandas as pd
from pathlib import Path
from core.dragon_eye.manager import DragonEyeManager
from datetime import datetime

def import_date_data(date_str: str):
    """导入指定日期的数据"""
    manager = DragonEyeManager()
    data_lake_dir = Path(f'quant/data/data_lake/{date_str}')
    
    if not data_lake_dir.exists():
        print(f"数据目录不存在: {data_lake_dir}")
        return
    
    # 1. 导入涨停股票数据
    limit_up_path = data_lake_dir / 'limit_up_filter.json'
    if limit_up_path.exists():
        with open(limit_up_path, 'r', encoding='utf-8') as f:
            limit_up_data = json.load(f)
        
        stocks = limit_up_data.get('data', {}).get('stocks', [])
        if stocks:
            df_stocks = pd.DataFrame(stocks)
            df_stocks['trade_date'] = date_str
            
            # 确保列名正确
            column_mapping = {
                'code': 'stock_code',
                'name': 'stock_name',
                'continue_num': 'continue_num',
                'order_amount': 'order_amount',
                'turnover_rate': 'turnover_rate',
                'tags': 'tags',
                'is_regulation': 'is_regulation',
                'is_institution_buy': 'is_institution_buy',
                'leader_tag': 'leader_tag'
            }
            
            # 重命名列
            for old, new in column_mapping.items():
                if old in df_stocks.columns:
                    df_stocks[new] = df_stocks[old]
            
            manager.upsert_stocks(df_stocks)
            print(f"导入 {len(df_stocks)} 条股票数据")
    
    # 2. 导入市场情绪数据
    sentiment_path = data_lake_dir / 'market_sentiment_cycle.json'
    if sentiment_path.exists():
        with open(sentiment_path, 'r', encoding='utf-8') as f:
            sentiment_data = json.load(f)
        
        items = sentiment_data.get('data', [])
        if items:
            df_sentiment = pd.DataFrame(items)
            df_sentiment['trade_date'] = date_str
            manager.upsert_sentiment(df_sentiment)
            print(f"导入 {len(df_sentiment)} 条情绪数据")
    
    print(f"日期 {date_str} 数据导入完成!")


if __name__ == '__main__':
    # 导入 2025-12-09 的数据
    import_date_data('2025-12-09')
    
    # 验证数据
    manager = DragonEyeManager()
    df = manager.get_historical_dragon('2025-12-01', '2025-12-31')
    print(f"\n验证: 查询到 {len(df)} 条股票数据")
    if len(df) > 0:
        print(df.head())
