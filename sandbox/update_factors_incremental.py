"""
增量更新因子和涨跌停状态

逻辑：
1. 从 stock_daily 获取最新数据（到 2026-02-27）
2. 检查 factor/limit_status 库的最后日期
3. 只计算缺失日期的数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from config.config import Config
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


def get_stock_daily_dates():
    """获取 stock_daily 的日期范围"""
    arctic = get_arctic_instance_for_library('stock_daily')
    lib = arctic['stock_daily']
    symbols = lib.list_symbols()
    
    all_dates = set()
    for sym in symbols[:100]:  # 采样检查
        try:
            data = lib.read(sym)
            df = data.data
            for d in df.index:
                all_dates.add(d.strftime('%Y-%m-%d'))
        except:
            pass
    
    return sorted(all_dates)


def get_factor_last_date():
    """获取因子库的最后日期"""
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    symbols = lib.list_symbols()
    
    if not symbols:
        return None
    
    # 检查第一个 symbol 的最后日期
    try:
        data = lib.read(symbols[0])
        return data.data.index.max().strftime('%Y-%m-%d')
    except:
        return None


def get_limit_status_last_date():
    """获取涨跌停状态库的最后日期"""
    arctic = get_arctic_instance_for_library('limit_status')
    lib = arctic['limit_status']
    symbols = lib.list_symbols()
    
    if not symbols:
        return None
    
    try:
        data = lib.read(symbols[0])
        return data.data.index.max().strftime('%Y-%m-%d')
    except:
        return None


def compute_factors_incremental():
    """增量计算因子"""
    logger.info("=" * 60)
    logger.info("增量计算因子")
    logger.info("=" * 60)
    
    # 获取 stock_daily 数据
    arctic_daily = get_arctic_instance_for_library('stock_daily')
    lib_daily = arctic_daily['stock_daily']
    symbols = lib_daily.list_symbols()
    logger.info(f"stock_daily 股票数: {len(symbols)}")
    
    # 获取因子库最后日期
    factor_last_date = get_factor_last_date()
    logger.info(f"因子库最后日期: {factor_last_date}")
    
    # 获取 stock_daily 最后日期
    stock_last_date = None
    for sym in symbols[:10]:
        try:
            data = lib_daily.read(sym)
            d = data.data.index.max().strftime('%Y-%m-%d')
            if stock_last_date is None or d > stock_last_date:
                stock_last_date = d
        except:
            pass
    
    logger.info(f"stock_daily 最后日期: {stock_last_date}")
    
    if factor_last_date and stock_last_date:
        if factor_last_date >= stock_last_date:
            logger.info("因子数据已是最新，无需更新")
            return 0
    
    # 需要更新的日期范围
    start_date = factor_last_date or "2020-01-01"
    end_date = stock_last_date
    logger.info(f"需要更新: {start_date} ~ {end_date}")
    
    # 获取因子库
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
            
            # 过滤需要更新的日期
            start_dt = pd.to_datetime(start_date)
            df_update = df[df.index > start_dt]
            
            if len(df_update) == 0:
                continue
            
            # 计算技术指标因子
            factors = compute_technical_factors(df_update)
            
            if len(factors) > 0:
                # 写入因子库
                symbol_name = f"momentum_{sym}"
                lib_factor.write(symbol_name, factors, metadata={"ts_code": sym})
                total_rows += len(factors)
            
            if (i + 1) % 500 == 0:
                logger.info(f"  进度: {i+1}/{len(symbols)}")
                
        except Exception as e:
            logger.warning(f"  {sym} 失败: {e}")
    
    logger.info(f"✓ 因子更新完成: {total_rows:,} 行")
    return total_rows


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标因子"""
    factors = pd.DataFrame(index=df.index)
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    factors['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MA
    for period in [5, 10, 20, 60]:
        factors[f'ma{period}'] = df['close'].rolling(window=period).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    factors['macd_dif'] = ema12 - ema26
    factors['macd_dea'] = factors['macd_dif'].ewm(span=9, adjust=False).mean()
    factors['macd_histogram'] = factors['macd_dif'] - factors['macd_dea']
    
    # 布林带
    factors['boll_mid'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    factors['boll_upper'] = factors['boll_mid'] + 2 * std
    factors['boll_lower'] = factors['boll_mid'] - 2 * std
    
    # ATR
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    factors['atr_14'] = tr.rolling(window=14).mean()
    
    return factors.dropna()


def compute_limit_status_incremental():
    """增量计算涨跌停状态"""
    logger.info("\n" + "=" * 60)
    logger.info("增量计算涨跌停状态")
    logger.info("=" * 60)
    
    # 获取 stock_daily 数据
    arctic_daily = get_arctic_instance_for_library('stock_daily')
    lib_daily = arctic_daily['stock_daily']
    symbols = lib_daily.list_symbols()
    
    # 获取涨跌停状态库最后日期
    limit_last_date = get_limit_status_last_date()
    logger.info(f"涨跌停状态库最后日期: {limit_last_date}")
    
    if limit_last_date:
        # 检查是否需要更新
        stock_last_date = None
        for sym in symbols[:10]:
            try:
                data = lib_daily.read(sym)
                d = data.data.index.max().strftime('%Y-%m-%d')
                if stock_last_date is None or d > stock_last_date:
                    stock_last_date = d
            except:
                pass
        
        if limit_last_date >= stock_last_date:
            logger.info("涨跌停状态已是最新，无需更新")
            return 0
    
    # 获取涨跌停状态库
    arctic_limit = get_arctic_instance_for_library('limit_status')
    if 'limit_status' not in arctic_limit.list_libraries():
        arctic_limit.create_library('limit_status')
    lib_limit = arctic_limit['limit_status']
    
    # 计算涨跌停状态
    total_rows = 0
    start_date = limit_last_date or "2000-01-01"
    start_dt = pd.to_datetime(start_date)
    
    for i, sym in enumerate(symbols):
        try:
            data = lib_daily.read(sym)
            df = data.data
            
            # 过滤需要更新的日期
            df_update = df[df.index > start_dt]
            
            if len(df_update) == 0:
                continue
            
            # 计算涨跌停状态
            limit_status = pd.DataFrame(index=df_update.index)
            limit_status['is_limit_up'] = (df_update['close'] >= df_update['limit_up'] * 0.995).astype(int)
            limit_status['is_limit_down'] = (df_update['close'] <= df_update['limit_down'] * 1.005).astype(int)
            limit_status['is_opened'] = 1  # 默认已开盘
            limit_status['is_suspended'] = 0  # 默认未停牌
            
            # 写入
            lib_limit.write(sym, limit_status, metadata={"ts_code": sym})
            total_rows += len(limit_status)
            
            if (i + 1) % 500 == 0:
                logger.info(f"  进度: {i+1}/{len(symbols)}")
                
        except Exception as e:
            logger.warning(f"  {sym} 失败: {e}")
    
    logger.info(f"✓ 涨跌停状态更新完成: {total_rows:,} 行")
    return total_rows


if __name__ == "__main__":
    logger.info("开始增量更新因子和涨跌停状态...")
    
    # 1. 增量计算因子
    factor_rows = compute_factors_incremental()
    
    # 2. 增量计算涨跌停状态
    limit_rows = compute_limit_status_incremental()
    
    logger.info("\n" + "=" * 60)
    logger.info("更新完成!")
    logger.info(f"  因子数据: {factor_rows:,} 行")
    logger.info(f"  涨跌停状态: {limit_rows:,} 行")
    logger.info("=" * 60)
