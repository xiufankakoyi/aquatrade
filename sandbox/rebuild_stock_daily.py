"""
清理并重建 ArcticDB stock_daily 库

问题：数据格式混乱
- 有些是纯股票代码（如 000001）
- 有些是带后缀代码（如 000001.SZ）
- 有些是按日期存储（如 daily_20260225）

解决方案：
1. 删除旧的 stock_daily 库
2. 从 Parquet 重新迁移，使用 ts_code 作为 symbol
"""
import os
import sys
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
from loguru import logger
from config.config import Config
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def clean_stock_daily_library():
    """删除 stock_daily 库的旧数据"""
    logger.info("=" * 60)
    logger.info("步骤 1: 清理旧的 stock_daily 库")
    logger.info("=" * 60)
    
    stock_daily_path = Path(Config.ARCTICDB_PATH) / "stock_daily"
    if stock_daily_path.exists():
        logger.info(f"删除目录: {stock_daily_path}")
        shutil.rmtree(stock_daily_path)
        logger.info("✓ 旧数据已删除")
    else:
        logger.info("目录不存在，无需清理")


def migrate_from_parquet():
    """从 Parquet 迁移数据，使用 ts_code 作为 symbol"""
    logger.info("\n" + "=" * 60)
    logger.info("步骤 2: 从 Parquet 迁移数据")
    logger.info("=" * 60)
    
    parquet_path = Path(Config.PARQUET_DIR) / "stock_daily.parquet"
    if not parquet_path.exists():
        logger.error(f"❌ 文件不存在: {parquet_path}")
        return 0
    
    logger.info(f"读取 Parquet: {parquet_path}")
    df_pl = pl.read_parquet(parquet_path)
    logger.info(f"✓ 读取完成: {len(df_pl)} 行, {len(df_pl.columns)} 列")
    
    # 获取 ts_code 列表
    ts_codes = df_pl.select('ts_code').unique().to_series().to_list()
    logger.info(f"共 {len(ts_codes)} 只股票")
    
    # 获取 ArcticDB 实例
    arctic = get_arctic_instance_for_library('stock_daily')
    
    # 创建库
    if 'stock_daily' not in arctic.list_libraries():
        logger.info("创建 stock_daily 库...")
        arctic.create_library('stock_daily')
    
    lib = arctic['stock_daily']
    
    total_rows = 0
    for i, ts_code in enumerate(ts_codes):
        try:
            # 获取该股票的数据
            stock_data = df_pl.filter(pl.col('ts_code') == ts_code)
            if len(stock_data) == 0:
                continue
            
            # 转换为 pandas，设置日期索引
            df_pd = stock_data.to_pandas()
            df_pd['trade_date'] = pd.to_datetime(df_pd['trade_date'])
            df_pd = df_pd.set_index('trade_date').sort_index()
            
            # 写入 ArcticDB，使用 ts_code 作为 symbol
            lib.write(
                ts_code,  # symbol 格式: 000001.SZ
                df_pd,
                metadata={
                    "ts_code": ts_code,
                    "rows": len(df_pd),
                    "start_date": df_pd.index.min().strftime("%Y-%m-%d"),
                    "end_date": df_pd.index.max().strftime("%Y-%m-%d"),
                }
            )
            
            total_rows += len(df_pd)
            
            if (i + 1) % 500 == 0 or i == len(ts_codes) - 1:
                logger.info(f"  进度: {i+1}/{len(ts_codes)} 股票, {total_rows} 行")
                
        except Exception as e:
            logger.warning(f"  写入 {ts_code} 失败: {e}")
            continue
    
    logger.info(f"✅ 迁移完成: {total_rows} 行")
    return total_rows


def verify_data():
    """验证数据"""
    logger.info("\n" + "=" * 60)
    logger.info("步骤 3: 验证数据")
    logger.info("=" * 60)
    
    arctic = get_arctic_instance_for_library('stock_daily')
    lib = arctic['stock_daily']
    symbols = lib.list_symbols()
    
    logger.info(f"✓ stock_daily 库: {len(symbols)} 个 symbol")
    
    # 检查几个股票
    sample_symbols = ['000001.SZ', '600000.SH', '300001.SZ']
    for sym in sample_symbols:
        if sym in symbols:
            data = lib.read(sym)
            df = data.data
            logger.info(f"  {sym}: {df.index.min().strftime('%Y-%m-%d')} ~ {df.index.max().strftime('%Y-%m-%d')}, {len(df)} 行")
    
    return len(symbols)


if __name__ == "__main__":
    logger.info("开始重建 ArcticDB stock_daily 库...")
    
    # 1. 清理旧数据
    clean_stock_daily_library()
    
    # 2. 迁移数据
    rows = migrate_from_parquet()
    
    # 3. 验证
    symbols = verify_data()
    
    logger.info("\n" + "=" * 60)
    logger.info("重建完成!")
    logger.info(f"  - 股票数量: {symbols}")
    logger.info(f"  - 数据行数: {rows}")
    logger.info("=" * 60)
