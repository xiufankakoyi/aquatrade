"""
完整因子重算 - 包括技术指标和统计因子

从 Parquet 文件读取数据，计算所有因子后写入 factors_momentum_hot.parquet
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np
from datetime import datetime
from loguru import logger


def load_stock_data(start_date: str = None) -> pl.DataFrame:
    """从 Parquet 加载股票数据"""
    parquet_path = Path('data/parquet_data/stock_daily.parquet')
    
    df = pl.scan_parquet(parquet_path)
    
    if start_date:
        df = df.filter(pl.col('trade_date') >= start_date)
    
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
    
    if df['trade_date'].dtype == pl.Datetime:
        df = df.with_columns(
            pl.col('trade_date').dt.date().alias('trade_date')
        )
    
    df = df.sort('trade_date')
    df = df.with_columns(
        pl.col('close').pct_change().alias('_bench_ret')
    )
    
    return df.select(['trade_date', '_bench_ret'])


def calc_ma_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算均线因子"""
    for period in [5, 10, 20, 60, 120, 250]:
        col_name = f'ma{period}'
        if col_name not in df.columns:
            df = df.with_columns(
                pl.col('close').rolling_mean(window_size=period, min_samples=period).over('stock_code').alias(col_name)
            )
    return df


def calc_rsi_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算 RSI 因子"""
    for period in [6, 12, 24]:
        col_name = f'rsi_{period}'
        delta = pl.col('close').diff().over('stock_code')
        gain = pl.when(delta > 0).then(delta).otherwise(0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0)
        
        avg_gain = gain.rolling_mean(window_size=period, min_samples=period).over('stock_code')
        avg_loss = loss.rolling_mean(window_size=period, min_samples=period).over('stock_code')
        
        rs = avg_gain / avg_loss
        df = df.with_columns((100 - 100 / (1 + rs)).alias(col_name))
    
    return df


def calc_macd_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算 MACD 因子"""
    ema12 = pl.col('close').ewm_mean(span=12, min_samples=12).over('stock_code')
    ema26 = pl.col('close').ewm_mean(span=26, min_samples=26).over('stock_code')
    dif = ema12 - ema26
    dea = dif.ewm_mean(span=9, min_samples=9).over('stock_code')
    
    df = df.with_columns([
        dif.alias('macd_dif'),
        dea.alias('macd_dea'),
        (dif - dea).alias('macd_histogram')
    ])
    return df


def calc_kdj_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算 KDJ 因子"""
    n = 9
    low_n = pl.col('low').rolling_min(window_size=n, min_samples=n).over('stock_code')
    high_n = pl.col('high').rolling_max(window_size=n, min_samples=n).over('stock_code')
    
    rsv = (pl.col('close') - low_n) / (high_n - low_n + 1e-10) * 100
    
    k = rsv.ewm_mean(alpha=1/3, min_samples=n).over('stock_code')
    d = k.ewm_mean(alpha=1/3, min_samples=n).over('stock_code')
    j = 3 * k - 2 * d
    
    df = df.with_columns([
        k.alias('kdj_k'),
        d.alias('kdj_d'),
        j.alias('kdj_j')
    ])
    return df


def calc_boll_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算布林带因子"""
    n = 20
    mid = pl.col('close').rolling_mean(window_size=n, min_samples=n).over('stock_code')
    std = pl.col('close').rolling_std(window_size=n, min_samples=n).over('stock_code')
    
    df = df.with_columns([
        mid.alias('boll_mid'),
        (mid + 2 * std).alias('boll_upper'),
        (mid - 2 * std).alias('boll_lower')
    ])
    return df


def calc_atr_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算 ATR 因子"""
    n = 14
    tr = pl.max_horizontal([
        pl.col('high') - pl.col('low'),
        (pl.col('high') - pl.col('close').shift(1).over('stock_code')).abs(),
        (pl.col('low') - pl.col('close').shift(1).over('stock_code')).abs()
    ])
    
    df = df.with_columns(
        tr.rolling_mean(window_size=n, min_samples=n).over('stock_code').alias('atr_14')
    )
    return df


def calc_bias_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算 BIAS 因子"""
    for period in [5, 10, 20]:
        ma = pl.col('close').rolling_mean(window_size=period, min_samples=period).over('stock_code')
        df = df.with_columns(
            ((pl.col('close') - ma) / ma * 100).alias(f'bias_{period}')
        )
    return df


def calc_return_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算收益因子"""
    for days, col_name in [(5, 'return_5d'), (20, 'return_20d'), (60, 'return_60d')]:
        df = df.with_columns(
            ((pl.col('close') - pl.col('close').shift(days).over('stock_code')) / 
             pl.col('close').shift(days).over('stock_code') * 100).alias(col_name)
        )
    return df


def calc_risk_factors(df: pl.DataFrame) -> pl.DataFrame:
    """计算风险因子"""
    df = df.with_columns(
        pl.col('close').pct_change().over('stock_code').alias('_returns')
    )
    
    df = df.with_columns(
        (pl.col('_returns').rolling_std(window_size=20, min_samples=20).over('stock_code') * 
         np.sqrt(252) * 100).alias('volatility_20d')
    )
    
    df = df.with_columns(
        pl.col('close').rolling_max(window_size=20, min_samples=1).over('stock_code').alias('_rolling_max')
    )
    df = df.with_columns(
        ((pl.col('close') - pl.col('_rolling_max')) / pl.col('_rolling_max') * 100).alias('max_drawdown_20d')
    )
    df = df.drop(['_returns', '_rolling_max'])
    
    return df


def calc_stat_factors(df: pl.DataFrame, bench_df: pl.DataFrame) -> pl.DataFrame:
    """计算统计因子 - Beta、Alpha、相关系数"""
    df = df.with_columns(
        pl.col('close').pct_change().over('stock_code').alias('_stock_ret')
    )
    
    df = df.join(bench_df, on='trade_date', how='left')
    
    for window in [60, 120, 250]:
        df = calc_rolling_beta_alpha(df, window)
    
    df = df.drop(['_stock_ret', '_bench_ret'])
    
    return df


def calc_rolling_beta_alpha(df: pl.DataFrame, window: int) -> pl.DataFrame:
    """计算滚动 Beta、Alpha 和相关系数"""
    beta_col = f'beta_{window}d'
    alpha_col = f'alpha_{window}d'
    corr_col = f'corr_{window}d'
    
    df = df.with_columns([
        (pl.col('_stock_ret') * pl.col('_bench_ret')).alias('_prod'),
        (pl.col('_bench_ret') ** 2).alias('_bench_sq'),
    ])
    
    df = df.with_columns([
        pl.col('_prod').rolling_sum(window_size=window, min_samples=window).over('stock_code').alias('_cov_sum'),
        pl.col('_bench_ret').rolling_sum(window_size=window, min_samples=window).alias('_bench_sum'),
        pl.col('_bench_sq').rolling_sum(window_size=window, min_samples=window).alias('_bench_var_sum'),
        pl.col('_stock_ret').rolling_sum(window_size=window, min_samples=window).over('stock_code').alias('_stock_sum'),
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
        pl.col('_stock_ret').rolling_std(window_size=window, min_samples=window).over('stock_code').alias('_stock_std'),
        pl.col('_bench_ret').rolling_std(window_size=window, min_samples=window).alias('_bench_std'),
    ])
    
    df = df.with_columns(
        (pl.col('_cov') / (pl.col('_stock_std') * pl.col('_bench_std') * (window - 1))).alias(corr_col)
    )
    
    drop_cols = ['_prod', '_bench_sq', '_cov_sum', '_bench_sum', '_bench_var_sum', 
                '_stock_sum', '_cov', '_bench_var', '_stock_std', '_bench_std']
    df = df.drop([c for c in drop_cols if c in df.columns])
    
    return df


def main():
    logger.info("=" * 70)
    logger.info("完整因子重算 - 包括技术指标和统计因子")
    logger.info("=" * 70)
    
    start_date = '2024-06-01'
    
    logger.info(f"日期范围: {start_date} ~ 最新")
    
    logger.info("加载股票数据...")
    stock_df = load_stock_data(start_date)
    logger.info(f"  股票数据: {len(stock_df)} 行, {stock_df['stock_code'].n_unique()} 只股票")
    
    logger.info("加载基准数据...")
    bench_df = load_benchmark_data()
    logger.info(f"  基准数据: {len(bench_df)} 行")
    
    logger.info("处理日期格式...")
    if stock_df['trade_date'].dtype == pl.String:
        stock_df = stock_df.with_columns(
            pl.col('trade_date').str.to_date('%Y-%m-%d').alias('trade_date')
        )
    
    if bench_df['trade_date'].dtype == pl.Datetime:
        bench_df = bench_df.with_columns(
            pl.col('trade_date').dt.date().alias('trade_date')
        )
    
    logger.info("排序数据...")
    df = stock_df.sort(['stock_code', 'trade_date'])
    
    logger.info("过滤无效数据...")
    df = df.filter(pl.col('close').is_not_null())
    logger.info(f"  过滤后: {len(df)} 行")
    
    logger.info("计算技术指标...")
    df = calc_ma_factors(df)
    logger.info("  MA 完成")
    df = calc_rsi_factors(df)
    logger.info("  RSI 完成")
    df = calc_macd_factors(df)
    logger.info("  MACD 完成")
    df = calc_kdj_factors(df)
    logger.info("  KDJ 完成")
    df = calc_boll_factors(df)
    logger.info("  BOLL 完成")
    df = calc_atr_factors(df)
    logger.info("  ATR 完成")
    df = calc_bias_factors(df)
    logger.info("  BIAS 完成")
    
    logger.info("计算收益和风险因子...")
    df = calc_return_factors(df)
    df = calc_risk_factors(df)
    
    logger.info("计算统计因子...")
    df = calc_stat_factors(df, bench_df)
    logger.info("  Beta/Alpha/Corr 完成")
    
    factor_cols = ['trade_date', 'stock_code',
                   'ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250',
                   'rsi_6', 'rsi_12', 'rsi_24',
                   'macd_dif', 'macd_dea', 'macd_histogram',
                   'kdj_k', 'kdj_d', 'kdj_j',
                   'boll_mid', 'boll_upper', 'boll_lower',
                   'atr_14', 'bias_5', 'bias_10', 'bias_20',
                   'return_5d', 'return_20d', 'return_60d',
                   'volatility_20d', 'max_drawdown_20d',
                   'beta_60d', 'beta_120d', 'beta_250d',
                   'alpha_60d', 'alpha_120d', 'alpha_250d',
                   'corr_60d', 'corr_120d', 'corr_250d']
    
    factor_df = df.select([c for c in factor_cols if c in df.columns])
    
    factor_df = factor_df.with_columns(
        pl.col('trade_date').dt.strftime('%Y-%m-%d').alias('trade_date')
    )
    
    output_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    factor_df.write_parquet(output_path)
    
    logger.info(f"保存到: {output_path}")
    logger.info(f"总行数: {len(factor_df)}")
    
    latest_date = factor_df['trade_date'].max()
    sample = factor_df.filter(pl.col('trade_date') == latest_date).head(5)
    logger.info(f"样本数据 ({latest_date}):")
    print(sample.select(['stock_code', 'beta_60d', 'alpha_60d', 'corr_60d']))
    
    logger.info("=" * 70)
    logger.info("因子重算完成!")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
