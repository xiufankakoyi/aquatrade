#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 Parquet 数据高效迁移到 ArcticDB - 内存优化版

使用分批处理避免内存不足

使用示例:
    python sandbox/migrate_stock_daily_memory_efficient.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
from loguru import logger
from config.config import Config
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def migrate_stock_daily_memory_efficient(batch_size: int = 100):
    """内存优化版：按股票代码分批迁移
    
    Args:
        batch_size: 每批处理的股票数量
    """
    logger.info("=" * 60)
    logger.info("迁移股票日线数据到 ArcticDB (内存优化版)")
    logger.info("=" * 60)
    
    parquet_path = Path(Config.PARQUET_DIR) / "stock_daily.parquet"
    if not parquet_path.exists():
        logger.error(f"文件不存在: {parquet_path}")
        return 0
    
    # 获取所有股票代码（只扫描，不加载数据）
    logger.info("扫描股票代码...")
    stock_codes = pl.scan_parquet(parquet_path).select('stock_code').unique().collect().to_series().to_list()
    logger.info(f"共 {len(stock_codes)} 只股票")
    
    # 获取 ArcticDB 库
    arctic = get_arctic_instance_for_library("stock_daily")
    lib = arctic["stock_daily"]
    
    total_rows = 0
    total_stocks = len(stock_codes)
    
    # 分批处理
    for batch_start in range(0, total_stocks, batch_size):
        batch_end = min(batch_start + batch_size, total_stocks)
        batch_codes = stock_codes[batch_start:batch_end]
        
        logger.info(f"处理批次 {batch_start//batch_size + 1}: 股票 {batch_start+1}-{batch_end}")
        
        # 只读取当前批次的数据
        try:
            df_batch = pl.scan_parquet(parquet_path).filter(
                pl.col('stock_code').is_in(batch_codes)
            ).collect()
            
            if df_batch.is_empty():
                continue
            
            # 转换为 pandas
            df_pd = df_batch.to_pandas()
            
            if 'trade_date' in df_pd.columns:
                df_pd['trade_date'] = pd.to_datetime(df_pd['trade_date'])
                df_pd = df_pd.set_index('trade_date')
            
            # 按股票代码写入
            for stock_code in batch_codes:
                stock_data = df_pd[df_pd['stock_code'] == stock_code].copy()
                
                if stock_data.empty:
                    continue
                
                try:
                    # 确保索引是 datetime
                    if not isinstance(stock_data.index, pd.DatetimeIndex):
                        continue
                    
                    stock_data = stock_data.sort_index()
                    
                    # 写入 ArcticDB
                    lib.write(
                        stock_code,
                        stock_data,
                        metadata={
                            "stock_code": stock_code,
                            "rows": len(stock_data),
                            "source": "parquet_migration_v2"
                        }
                    )
                    total_rows += len(stock_data)
                    
                except Exception as e:
                    logger.warning(f"写入 {stock_code} 失败: {e}")
                    continue
            
            logger.info(f"  批次完成，累计: {total_rows} 行")
            
            # 释放内存
            del df_batch, df_pd
            
        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            continue
    
    logger.info(f"迁移完成: {total_stocks} 只股票, {total_rows} 行")
    return total_rows


if __name__ == '__main__':
    migrate_stock_daily_memory_efficient(batch_size=50)
