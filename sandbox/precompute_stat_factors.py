"""
预计算统计因子 - Beta、Alpha、相关系数

从 Parquet 文件读取数据，计算统计因子后写入 factors_momentum_hot.parquet
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


def load_stock_data(start_date: str = None, end_date: str = None) -> pl.DataFrame:
    """从 Parquet 加载股票数据"""
    parquet_path = Path('data/parquet_data/stock_daily.parquet')
    
    df = pl.scan_parquet(parquet_path)
    
    if start_date:
        df = df.filter(pl.col('trade_date') >= start_date)
    if end_date:
        df = df.filter(pl.col('trade_date') <= end_date)
    
    return df.collect()


def load_benchmark_data() -> pl.DataFrame:
    """加载沪深300基准数据"""
    parquet_path = Path('data/parquet_data/hs300_daily.parquet')
    
    df = pl.scan_parquet(parquet_path).collect()
    
    if 'date' in df.columns:
        df = df.rename({'date': 'trade_date'})
    
    if df['trade_date'].dtype == pl.String:
        df = df.with_columns(
            pl.col('trade_date').str.to_date('%Y-%m-%d').alias('trade_date')
        )
    
    df = df.sort('trade_date')
    df = df.with_columns(
        pl.col('close').pct_change().alias('_bench_ret')
    )
    
    return df.select(['trade_date', '_bench_ret'])


def load_existing_factors() -> pl.DataFrame:
    """加载现有因子数据"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    if not parquet_path.exists():
        return None
    
    df = pl.scan_parquet(parquet_path).collect()
    
    if df['trade_date'].dtype == pl.String:
        df = df.with_columns(
            pl.col('trade_date').str.to_date('%Y-%m-%d').alias('trade_date')
        )
    
    return df


def calc_rolling_beta_alpha(df: pl.DataFrame, window: int) -> pl.DataFrame:
    """
    计算滚动 Beta、Alpha 和相关系数
    """
    beta_col = f'beta_{window}d'
    alpha_col = f'alpha_{window}d'
    corr_col = f'corr_{window}d'
    
    logger.info(f"  计算 {window} 日统计因子...")
    
    df = df.with_columns([
        (pl.col('_stock_ret') * pl.col('_bench_ret')).alias('_prod'),
        (pl.col('_bench_ret') ** 2).alias('_bench_sq'),
    ])
    
    df = df.with_columns([
        pl.col('_prod').rolling_sum(window_size=window, min_periods=window).over('stock_code').alias('_cov_sum'),
        pl.col('_bench_ret').rolling_sum(window_size=window, min_periods=window).alias('_bench_sum'),
        pl.col('_bench_sq').rolling_sum(window_size=window, min_periods=window).alias('_bench_var_sum'),
        pl.col('_stock_ret').rolling_sum(window_size=window, min_periods=window).over('stock_code').alias('_stock_sum'),
    ])
    
    df = df.with_columns([
        (pl.col('_cov_sum') - pl.col('_bench_sum') * pl.col('_stock_sum') / window).alias('_cov'),
        (pl.col('_bench_var_sum') - pl.col('_bench_sum') ** 2 / window).alias('_bench_var'),
    ])
    
    df = df.with_columns(
        (pl.col('_cov') / pl.col('_bench_var')).alias(beta_col)
    )
    
    df = df.with_columns(
        (pl.col('_stock_sum') / window - pl.col(beta_col) * pl.col('_bench_sum') / window).alias(alpha_col)
    )
    
    df = df.with_columns([
        pl.col('_stock_ret').rolling_std(window_size=window, min_periods=window).over('stock_code').alias('_stock_std'),
        pl.col('_bench_ret').rolling_std(window_size=window, min_periods=window).alias('_bench_std'),
    ])
    
    df = df.with_columns(
        (pl.col('_cov') / (pl.col('_stock_std') * pl.col('_bench_std') * (window - 1))).alias(corr_col)
    )
    
    drop_cols = ['_prod', '_bench_sq', '_cov_sum', '_bench_sum', '_bench_var_sum', 
                '_stock_sum', '_cov', '_bench_var', '_stock_std', '_bench_std']
    df = df.drop([c for c in drop_cols if c in df.columns])
    
    return df


def calc_return_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算收益因子"""
    logger.info("  计算收益因子...")
    
    for days, col_name in [(5, 'return_5d'), (20, 'return_20d'), (60, 'return_60d')]:
        df = df.with_columns(
            ((pl.col('close') - pl.col('close').shift(days).over('stock_code')) / 
             pl.col('close').shift(days).over('stock_code') * 100).alias(col_name)
        )
    
    return df


def calc_risk_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算风险因子"""
    logger.info("  计算风险因子...")
    
    df = df.with_columns(
        pl.col('close').pct_change().over('stock_code').alias('_returns')
    )
    
    df = df.with_columns(
        (pl.col('_returns').rolling_std(window_size=20, min_periods=20).over('stock_code') * 
         np.sqrt(252) * 100).alias('volatility_20d')
    )
    
    df = df.with_columns(
        pl.col('close').rolling_max(window_size=20, min_periods=1).over('stock_code').alias('_rolling_max')
    )
    df = df.with_columns(
        ((pl.col('close') - pl.col('_rolling_max')) / pl.col('_rolling_max') * 100).alias('max_drawdown_20d')
    )
    df = df.drop(['_returns', '_rolling_max'])
    
    return df


def main():
    logger.info("=" * 70)
    logger.info("预计算统计因子 - Beta/Alpha/Corr")
    logger.info("=" * 70)
    
    start_date = '2025-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"日期范围: {start_date} ~ {end_date}")
    
    logger.info("加载股票数据...")
    stock_df = load_stock_data(start_date, end_date)
    logger.info(f"  股票数据: {len(stock_df)} 行, {stock_df['stock_code'].n_unique()} 只股票")
    
    logger.info("加载基准数据...")
    bench_df = load_benchmark_data()
    logger.info(f"  基准数据: {len(bench_df)} 行")
    
    logger.info("加载现有因子数据...")
    existing_factors = load_existing_factors()
    if existing_factors is not None:
        logger.info(f"  现有因子: {len(existing_factors)} 行")
    
    logger.info("合并数据...")
    df = stock_df.sort(['stock_code', 'trade_date'])
    
    if df['trade_date'].dtype == pl.String:
        df = df.with_columns(
            pl.col('trade_date').str.to_date('%Y-%m-%d').alias('trade_date')
        )
    
    if df['trade_date'].dtype == pl.Date:
        df = df.with_columns(
            pl.col('trade_date').cast(pl.Datetime).alias('trade_date')
        )
    
    df = df.with_columns(
        pl.col('close').pct_change().over('stock_code').alias('_stock_ret')
    )
    
    if bench_df['trade_date'].dtype == pl.Date:
        bench_df = bench_df.with_columns(
            pl.col('trade_date').cast(pl.Datetime).alias('trade_date')
        )
    
    df = df.join(bench_df, on='trade_date', how='left')
    
    logger.info("计算统计因子...")
    for window in [60, 120, 250]:
        df = calc_rolling_beta_alpha(df, window)
    
    df = calc_return_factors(df)
    df = calc_risk_factors(df)
    
    df = df.drop(['_stock_ret', '_bench_ret'])
    
    stat_cols = ['trade_date', 'stock_code', 
                 'beta_60d', 'beta_120d', 'beta_250d',
                 'alpha_60d', 'alpha_120d', 'alpha_250d',
                 'corr_60d', 'corr_120d', 'corr_250d',
                 'return_5d', 'return_20d', 'return_60d',
                 'volatility_20d', 'max_drawdown_20d']
    
    stat_df = df.select([c for c in stat_cols if c in df.columns])
    
    logger.info("合并到现有因子数据...")
    if existing_factors is not None:
        if 'stock_code' in existing_factors.columns:
            existing_factors = existing_factors.with_columns(
                pl.col('stock_code').str.split('.').list.get(0).alias('stock_code')
            )
        
        if existing_factors['trade_date'].dtype == pl.String:
            existing_factors = existing_factors.with_columns(
                pl.col('trade_date').str.to_date('%Y-%m-%d').alias('trade_date')
            )
        
        if existing_factors['trade_date'].dtype == pl.Date:
            existing_factors = existing_factors.with_columns(
                pl.col('trade_date').cast(pl.Datetime('us')).alias('trade_date')
            )
        
        if stat_df['trade_date'].dtype != existing_factors['trade_date'].dtype:
            stat_df = stat_df.with_columns(
                pl.col('trade_date').cast(existing_factors['trade_date'].dtype).alias('trade_date')
            )
        
        for col in stat_cols[2:]:
            if col in existing_factors.columns:
                existing_factors = existing_factors.drop(col)
        
        merged = existing_factors.join(
            stat_df,
            on=['trade_date', 'stock_code'],
            how='left'
        )
    else:
        merged = stat_df
    
    output_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    if 'trade_date' in merged.columns and merged['trade_date'].dtype != pl.String:
        merged = merged.with_columns(
            pl.col('trade_date').dt.strftime('%Y-%m-%d').alias('trade_date')
        )
    
    merged.write_parquet(output_path)
    
    logger.info(f"保存到: {output_path}")
    logger.info(f"总行数: {len(merged)}")
    logger.info(f"列: {merged.columns}")
    
    sample = merged.filter(pl.col('trade_date') == end_date).head(3)
    logger.info(f"样本数据 ({end_date}):")
    print(sample.select(['stock_code', 'beta_60d', 'alpha_60d', 'corr_60d', 'return_5d']))
    
    logger.info("=" * 70)
    logger.info("预计算完成!")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
