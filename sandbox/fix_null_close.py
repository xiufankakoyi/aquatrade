"""
修复 stock_daily 中 close 为 null 的记录
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import numpy as np
from loguru import logger
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def find_null_close_symbols():
    """找出所有 close 为 null 的 symbol"""
    arctic = get_arctic_instance_for_library('stock_daily')
    lib = arctic['stock_daily']
    
    symbols = lib.list_symbols()
    problem_symbols = []
    
    logger.info(f"检查 {len(symbols)} 个 symbol...")
    
    for i, symbol in enumerate(symbols):
        try:
            data = lib.read(symbol)
            df = data.data
            
            if hasattr(df, 'to_pandas'):
                df = df.to_pandas()
            
            if 'close' in df.columns:
                null_count = df['close'].isna().sum()
                if null_count > 0:
                    null_dates = df[df['close'].isna()].index.tolist()
                    problem_symbols.append({
                        'symbol': symbol,
                        'null_count': null_count,
                        'null_dates': [str(d) for d in null_dates]
                    })
                    
            if (i + 1) % 500 == 0:
                logger.info(f"  进度: {i+1}/{len(symbols)}")
                
        except Exception as e:
            logger.warning(f"  {symbol} 检查失败: {e}")
    
    return problem_symbols


def fix_null_close(symbol: str, null_dates: list):
    """修复单个 symbol 的 null close"""
    arctic = get_arctic_instance_for_library('stock_daily')
    lib = arctic['stock_daily']
    
    try:
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        original_nulls = df['close'].isna().sum()
        
        # 使用前值填充
        df['close'] = df['close'].ffill()
        
        # 如果还有 null，使用后值填充
        df['close'] = df['close'].bfill()
        
        # 同样处理 open, high, low
        for col in ['open', 'high', 'low']:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()
        
        # 写回
        lib.write(symbol, df)
        
        new_nulls = df['close'].isna().sum()
        
        return {
            'symbol': symbol,
            'original_nulls': original_nulls,
            'new_nulls': new_nulls,
            'fixed': original_nulls - new_nulls
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'error': str(e)
        }


def main():
    logger.info("=" * 70)
    logger.info("修复 stock_daily 中 close 为 null 的记录")
    logger.info("=" * 70)
    
    # 找出问题 symbol
    problem_symbols = find_null_close_symbols()
    
    logger.info(f"\n发现 {len(problem_symbols)} 个 symbol 存在 close 为 null:")
    for p in problem_symbols[:10]:
        logger.info(f"  {p['symbol']}: {p['null_count']} null 在 {p['null_dates'][:3]}")
    
    if len(problem_symbols) > 10:
        logger.info(f"  ... 还有 {len(problem_symbols) - 10} 个")
    
    # 修复
    logger.info("\n开始修复...")
    fixed_count = 0
    
    for p in problem_symbols:
        result = fix_null_close(p['symbol'], p['null_dates'])
        if 'fixed' in result and result['fixed'] > 0:
            fixed_count += result['fixed']
            logger.info(f"  {result['symbol']}: 修复了 {result['fixed']} 条")
    
    logger.info(f"\n修复完成! 共修复 {fixed_count} 条记录")


if __name__ == '__main__':
    main()
