"""
更新涨跌停状态和因子数据

数据来源：Parquet 备份文件
目标：ArcticDB 独立库实例
"""
import os
import sys
import time
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
from loguru import logger
from config.config import Config
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def update_limit_status():
    """更新涨跌停状态数据"""
    logger.info("=" * 60)
    logger.info("更新涨跌停状态数据")
    logger.info("=" * 60)
    
    parquet_path = Path(Config.PARQUET_DIR) / "stock_limit_status.parquet"
    if not parquet_path.exists():
        logger.error(f"文件不存在: {parquet_path}")
        return 0
    
    # 读取 Parquet
    logger.info(f"读取: {parquet_path}")
    df = pl.read_parquet(parquet_path)
    logger.info(f"总行数: {len(df):,}")
    
    if df.is_empty():
        logger.warning("数据为空")
        return 0
    
    # 获取日期范围
    dates = df.select('trade_date').unique().to_series().to_list()
    logger.info(f"日期范围: {min(dates)} ~ {max(dates)}")
    
    # 删除旧库并重建
    lib_path = Path(Config.ARCTICDB_PATH) / "limit_status"
    if lib_path.exists():
        logger.info(f"删除旧库: {lib_path}")
        shutil.rmtree(lib_path)
    
    # 获取 ArcticDB 实例
    arctic = get_arctic_instance_for_library('limit_status')
    
    # 创建库
    if 'limit_status' not in arctic.list_libraries():
        arctic.create_library('limit_status')
    
    lib = arctic['limit_status']
    
    # 按 stock_code 分组写入
    logger.info("按股票代码写入...")
    stock_codes = df.select('stock_code').unique().to_series().to_list()
    logger.info(f"股票数量: {len(stock_codes)}")
    
    total_rows = 0
    for i, stock_code in enumerate(stock_codes):
        try:
            stock_df = df.filter(pl.col('stock_code') == stock_code)
            if len(stock_df) == 0:
                continue
            
            # 转换为 pandas，设置日期索引
            df_pd = stock_df.to_pandas()
            df_pd['trade_date'] = pd.to_datetime(df_pd['trade_date'])
            df_pd = df_pd.set_index('trade_date').sort_index()
            
            # symbol 格式: 000001.SZ (需要添加后缀)
            # 根据 stock_code 判断市场
            if stock_code.startswith('6'):
                symbol = f"{stock_code}.SH"
            else:
                symbol = f"{stock_code}.SZ"
            
            lib.write(symbol, df_pd, metadata={"stock_code": stock_code, "rows": len(df_pd)})
            total_rows += len(df_pd)
            
            if (i + 1) % 500 == 0:
                logger.info(f"  进度: {i+1}/{len(stock_codes)}")
        except Exception as e:
            logger.warning(f"  {stock_code} 失败: {e}")
    
    logger.info(f"✓ 涨跌停状态更新完成: {total_rows:,} 行")
    return total_rows


def update_factors():
    """更新因子数据"""
    logger.info("\n" + "=" * 60)
    logger.info("更新因子数据")
    logger.info("=" * 60)
    
    factor_files = [
        ("momentum", "factors_momentum_hot.parquet"),
        ("valuation", "factors_valuation_hot.parquet"),
    ]
    
    total_rows = 0
    
    for factor_type, filename in factor_files:
        parquet_path = Path(Config.PARQUET_DIR) / filename
        if not parquet_path.exists():
            logger.warning(f"文件不存在: {parquet_path}")
            continue
        
        logger.info(f"\n处理: {factor_type}")
        logger.info(f"读取: {parquet_path}")
        
        df = pl.read_parquet(parquet_path)
        logger.info(f"总行数: {len(df):,}")
        
        if df.is_empty():
            continue
        
        # 获取日期范围
        dates = df.select('trade_date').unique().to_series().to_list()
        logger.info(f"日期范围: {min(dates)} ~ {max(dates)}")
        
        # 获取 ArcticDB 实例
        arctic = get_arctic_instance_for_library('factor')
        
        # 创建库
        if 'factor' not in arctic.list_libraries():
            arctic.create_library('factor')
        
        lib = arctic['factor']
        
        # 按 stock_code 分组写入
        stock_codes = df.select('stock_code').unique().to_series().to_list()
        logger.info(f"股票数量: {len(stock_codes)}")
        
        for i, stock_code in enumerate(stock_codes):
            try:
                stock_df = df.filter(pl.col('stock_code') == stock_code)
                if len(stock_df) == 0:
                    continue
                
                # 转换为 pandas，设置日期索引
                df_pd = stock_df.to_pandas()
                df_pd['trade_date'] = pd.to_datetime(df_pd['trade_date'])
                df_pd = df_pd.set_index('trade_date').sort_index()
                
                # symbol 格式: momentum_000001.SZ
                # 根据 stock_code 判断市场
                if stock_code.startswith('6'):
                    ts_code = f"{stock_code}.SH"
                else:
                    ts_code = f"{stock_code}.SZ"
                
                symbol = f"{factor_type}_{ts_code}"
                lib.write(symbol, df_pd, metadata={"ts_code": ts_code, "factor_type": factor_type})
                total_rows += len(df_pd)
                
                if (i + 1) % 500 == 0:
                    logger.info(f"  进度: {i+1}/{len(stock_codes)}")
            except Exception as e:
                logger.warning(f"  {stock_code} 失败: {e}")
        
        logger.info(f"✓ {factor_type} 因子更新完成")
    
    logger.info(f"\n✓ 因子数据更新完成: {total_rows:,} 行")
    return total_rows


if __name__ == "__main__":
    logger.info("开始更新涨跌停状态和因子数据...")
    logger.info("注意：需要先停止后端服务，避免数据库锁定")
    
    # 1. 更新涨跌停状态
    limit_rows = update_limit_status()
    
    # 2. 更新因子数据
    factor_rows = update_factors()
    
    logger.info("\n" + "=" * 60)
    logger.info("更新完成!")
    logger.info(f"  涨跌停状态: {limit_rows:,} 行")
    logger.info(f"  因子数据: {factor_rows:,} 行")
    logger.info("=" * 60)
