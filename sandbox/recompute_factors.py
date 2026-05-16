"""
重新计算因子数据（基于 stock_daily 完整数据）

问题：之前从 Parquet 迁移的因子数据只到 2025-11-20
解决：基于 stock_daily（到 2026-02-27）重新计算
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import shutil
import pandas as pd
import numpy as np
from loguru import logger
from config.config import Config
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def recompute_all_factors():
    """基于 stock_daily 重新计算所有因子"""
    logger.info("=" * 60)
    logger.info("重新计算因子数据")
    logger.info("=" * 60)
    
    # 删除旧的因子库
    factor_path = Path(Config.ARCTICDB_PATH) / "factor"
    if factor_path.exists():
        logger.info(f"删除旧因子库: {factor_path}")
        shutil.rmtree(factor_path)
    
    # 获取 stock_daily 数据
    arctic_daily = get_arctic_instance_for_library('stock_daily')
    lib_daily = arctic_daily['stock_daily']
    symbols = lib_daily.list_symbols()
    logger.info(f"stock_daily 股票数: {len(symbols)}")
    
    # 创建因子库
    arctic_factor = get_arctic_instance_for_library('factor')
    if 'factor' not in arctic_factor.list_libraries():
        arctic_factor.create_library('factor')
    lib_factor = arctic_factor['factor']
    
    # 计算因子
    total_rows = 0
    for i, sym in enumerate(symbols):
        try:
            data = lib_daily.read(sym)
            df = data.data
            
            if len(df) == 0:
                continue
            
            # 计算技术指标因子
            factors = compute_technical_factors(df)
            
            if len(factors) > 0:
                # 写入因子库
                symbol_name = f"momentum_{sym}"
                lib_factor.write(symbol_name, factors, metadata={"ts_code": sym})
                total_rows += len(factors)
            
            if (i + 1) % 500 == 0:
                logger.info(f"  进度: {i+1}/{len(symbols)}, 累计: {total_rows:,} 行")
                
        except Exception as e:
            logger.warning(f"  {sym} 失败: {e}")
    
    logger.info(f"✓ 因子计算完成: {total_rows:,} 行")
    return total_rows


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标因子"""
    factors = pd.DataFrame(index=df.index)
    
    close = df['close']
    high = df['high']
    low = df['low']
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.inf)
    factors['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MA
    for period in [5, 10, 20, 60, 120, 250]:
        factors[f'ma{period}'] = close.rolling(window=period).mean()
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    factors['macd_dif'] = ema12 - ema26
    factors['macd_dea'] = factors['macd_dif'].ewm(span=9, adjust=False).mean()
    factors['macd_histogram'] = factors['macd_dif'] - factors['macd_dea']
    
    # 布林带
    factors['boll_mid'] = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    factors['boll_upper'] = factors['boll_mid'] + 2 * std
    factors['boll_lower'] = factors['boll_mid'] - 2 * std
    
    # ATR (14)
    close_shifted = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - close_shifted).abs(),
        (low - close_shifted).abs()
    ], axis=1).max(axis=1)
    factors['atr_14'] = tr.rolling(window=14).mean()
    
    # KDJ
    low_14 = low.rolling(window=14).min()
    high_14 = high.rolling(window=14).max()
    rsv = (close - low_14) / (high_14 - low_14 + 1e-10) * 100
    factors['kdj_k'] = rsv.ewm(alpha=1/3, adjust=False).mean()
    factors['kdj_d'] = factors['kdj_k'].ewm(alpha=1/3, adjust=False).mean()
    factors['kdj_j'] = 3 * factors['kdj_k'] - 2 * factors['kdj_d']
    
    # BIAS
    for period in [5, 10, 20]:
        ma = close.rolling(window=period).mean()
        factors[f'bias_{period}'] = (close - ma) / ma * 100
    
    return factors.dropna()


if __name__ == "__main__":
    logger.info("开始重新计算因子数据...")
    
    rows = recompute_all_factors()
    
    logger.info("\n" + "=" * 60)
    logger.info("完成!")
    logger.info(f"  因子数据: {rows:,} 行")
    logger.info("=" * 60)
