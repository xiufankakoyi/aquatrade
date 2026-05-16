#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量导入 DragonEye 爬虫数据到 Parquet 存储"""

import json
import pandas as pd
from pathlib import Path
from core.dragon_eye.manager import DragonEyeManager
from datetime import datetime, timedelta
import time


def import_date_data(date_str: str, manager: DragonEyeManager = None):
    """导入指定日期的数据"""
    if manager is None:
        manager = DragonEyeManager()
    
    data_lake_dir = Path(f'quant/data/data_lake/{date_str}')
    
    if not data_lake_dir.exists():
        print(f"  ⚠️ 数据目录不存在: {data_lake_dir}")
        return False
    
    stocks_count = 0
    sentiment_count = 0
    
    # 1. 导入涨停股票数据
    limit_up_path = data_lake_dir / 'limit_up_filter.json'
    if limit_up_path.exists():
        try:
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
                }
                for old, new in column_mapping.items():
                    if old in df_stocks.columns:
                        df_stocks[new] = df_stocks[old]
                
                manager.upsert_stocks(df_stocks)
                stocks_count = len(df_stocks)
        except Exception as e:
            print(f"  ⚠️ 导入股票数据失败: {e}")
    
    # 2. 导入市场情绪数据
    sentiment_path = data_lake_dir / 'market_sentiment_cycle.json'
    if sentiment_path.exists():
        try:
            with open(sentiment_path, 'r', encoding='utf-8') as f:
                sentiment_data = json.load(f)
            
            items = sentiment_data.get('data', [])
            if items:
                df_sentiment = pd.DataFrame(items)
                df_sentiment['trade_date'] = date_str
                manager.upsert_sentiment(df_sentiment)
                sentiment_count = len(df_sentiment)
        except Exception as e:
            print(f"  ⚠️ 导入情绪数据失败: {e}")
    
    if stocks_count > 0 or sentiment_count > 0:
        print(f"  ✅ 导入 {stocks_count} 条股票, {sentiment_count} 条情绪数据")
        return True
    return False


def batch_import(start_date: str, end_date: str):
    """批量导入日期范围的数据"""
    manager = DragonEyeManager()
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    success_count = 0
    fail_count = 0
    
    print(f"\n{'='*60}")
    print(f"开始批量导入: {start_date} 到 {end_date}")
    print(f"{'='*60}\n")
    
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        print(f"[{date_str}] 处理中...", end="")
        
        if import_date_data(date_str, manager):
            success_count += 1
        else:
            fail_count += 1
        
        current += timedelta(days=1)
        time.sleep(0.1)  # 避免过于频繁
    
    print(f"\n{'='*60}")
    print(f"导入完成: 成功 {success_count} 天, 失败/无数据 {fail_count} 天")
    print(f"{'='*60}\n")
    
    # 验证总数据量
    df_stocks = manager.get_historical_dragon(start_date, end_date)
    df_sentiment = manager.get_market_sentiment(start_date, end_date)
    print(f"验证: 共 {len(df_stocks)} 条股票数据, {len(df_sentiment)} 条情绪数据")


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        batch_import(sys.argv[1], sys.argv[2])
    else:
        # 默认导入 2025-03-26 到 2025-04-20
        batch_import('2025-03-26', '2025-04-20')
