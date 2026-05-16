"""
将 stock_daily 库数据迁移到 daily 库
"""
from pathlib import Path
from arcticdb import Arctic
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def migrate_stock_daily_to_daily():
    base_path = Path('data/arctic_db')
    
    stock_daily_path = base_path / 'stock_daily'
    daily_path = base_path / 'daily'
    
    # 连接两个库
    logger.info("连接 ArcticDB...")
    arctic_stock = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')
    arctic_daily = Arctic(f'lmdb://{daily_path}?map_size=10GB')
    
    stock_lib = arctic_stock['stock_daily']
    symbols = stock_lib.list_symbols()
    
    logger.info(f"stock_daily 库共有 {len(symbols)} 只股票")
    logger.info(f"开始迁移到 daily 库...")
    
    # 获取或创建 daily 库
    if 'daily' in arctic_daily.list_libraries():
        daily_lib = arctic_daily['daily']
        logger.info("使用现有 daily 库")
    else:
        daily_lib = arctic_daily.create_library('daily')
        logger.info("创建新 daily 库")
    
    # 迁移数据
    success = 0
    failed = 0
    
    for i, symbol in enumerate(symbols):
        try:
            # 读取 stock_daily 数据
            item = stock_lib.read(symbol)
            df = item.data
            
            if df.empty:
                continue
            
            # 写入 daily 库
            daily_lib.write(symbol, df)
            success += 1
            
            if (i + 1) % 500 == 0:
                logger.info(f"进度: {i+1}/{len(symbols)}")
                
        except Exception as e:
            failed += 1
            logger.warning(f"  迁移 {symbol} 失败: {e}")
    
    logger.info(f"\n迁移完成!")
    logger.info(f"  成功: {success}")
    logger.info(f"  失败: {failed}")
    
    # 验证
    daily_symbols = daily_lib.list_symbols()
    logger.info(f"\ndaily 库现在共有 {len(daily_symbols)} 只股票")
    
    # 抽样验证
    for s in daily_symbols[:3]:
        item = daily_lib.read(s)
        df = item.data
        logger.info(f"  {s}: {df.index.min()} ~ {df.index.max()}, 共 {len(df)} 条")

if __name__ == "__main__":
    migrate_stock_daily_to_daily()
