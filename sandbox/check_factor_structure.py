"""
检查 factor 库中的数据结构
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def check_factor_structure():
    """检查 factor 库的数据结构"""
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    
    symbols = lib.list_symbols()
    logger.info(f"Factor 库中有 {len(symbols)} 个 symbol")
    
    # 检查几个样本
    for symbol in symbols[:3]:
        logger.info(f"\n检查 symbol: {symbol}")
        
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        logger.info(f"  列: {list(df.columns)}")
        logger.info(f"  行数: {len(df)}")
        logger.info(f"  日期范围: {df.index.min()} ~ {df.index.max()}")
        
        # 检查统计因子是否存在
        stat_cols = ['beta_60d', 'beta_120d', 'beta_250d', 
                    'alpha_60d', 'alpha_120d', 'alpha_250d',
                    'corr_60d', 'corr_120d', 'corr_250d']
        
        for col in stat_cols:
            if col in df.columns:
                null_count = df[col].isna().sum()
                logger.info(f"  {col}: 存在, null={null_count}/{len(df)}")
            else:
                logger.info(f"  {col}: 不存在")


if __name__ == '__main__':
    check_factor_structure()
