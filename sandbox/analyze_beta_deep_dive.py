"""
深度验证：高Beta与'好的更好'假说
基于用户提供的系统研究框架

分析内容：
1. 前瞻性市场方向分组 - 按未来市场涨跌分组
2. 动量因子 vs Beta 独立性检验
3. Jensen's Alpha 分析
4. 时间序列稳定性分段验证
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np
from loguru import logger
from datetime import datetime

def load_data():
    logger.info("加载数据...")
    factors_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "factors_momentum_hot.parquet")
    daily_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "stock_daily.parquet")

    daily_df = daily_df.select(['trade_date', 'stock_code', 'close', 'prev_close'])
    daily_df = daily_df.with_columns([
        ((pl.col('close') / pl.col('prev_close') - 1)).alias('daily_return')
    ])

    factors_df = factors_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))
    daily_df = daily_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))

    factors_df = factors_df.filter(pl.col('trade_date') >= '2020-01-01')

    if factors_df['trade_date'].dtype == pl.Date:
        factors_df = factors_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))
    if daily_df['trade_date'].dtype == pl.Date:
        daily_df = daily_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))

    df = factors_df.join(daily_df, on=['trade_date', 'stock_code'], how='left')
    df = df.sort(['stock_code', 'trade_date'])

    for window in [5, 20, 60]:
        df = df.with_columns(
            (pl.col('close').shift(-window) / pl.col('close') - 1).alias(f'future_ret_{window}d')
        )

    df = df.filter(pl.col('beta_60d').is_not_null())
    logger.info(f"合并后数据: {df.shape[0]} 行")

    # 计算市场收益率
    market_ret = df.group_by('trade_date').agg([
        (pl.col('daily_return') * pl.col('close')).sum() / pl.col('close').sum()
    ]).rename({'daily_return': 'market_return'})

    df = df.join(market_ret, on='trade_date', how='left')

    # 计算未来市场收益
    df = df.sort('trade_date')
    df = df.with_columns(
        pl.col('market_return').shift(-5).alias('future_market_ret_5d')
    )

    # 股票Beta分组
    stock_beta = df.group_by('stock_code').agg([
        pl.col('beta_60d').median().alias('median_beta')
    ])
    stock_beta = stock_beta.with_columns([
        pl.when(pl.col('median_beta') < 0.8).then(pl.lit('low'))
        .when(pl.col('median_beta') > 1.2).then(pl.lit('high'))
        .otherwise(pl.lit('mid'))
        .alias('beta_group')
    ])
    df = df.join(stock_beta.select(['stock_code', 'beta_group']), on='stock_code', how='left')

    # 计算动量因子（过去60日收益）
    df = df.with_columns(
        (pl.col('close') / pl.col('close').shift(60) - 1).alias('momentum_60d')
    )

    return df

def analyze_forward_market_direction(df):
    """1. 前瞻性市场方向分组"""
    logger.info("\n" + "=" * 70)
    logger.info("分析1: 前瞻性市场方向分组（按未来市场涨跌）")
    logger.info("=" * 70)

    df = df.filter(pl.col('future_market_ret_5d').is_not_null())

    df = df.with_columns([
        pl.when(pl.col('future_market_ret_5d') > 0).then(pl.lit('future_up'))
        .otherwise(pl.lit('future_down'))
        .alias('future_market_dir')
    ])

    for mkt_dir in ['future_up', 'future_down']:
        label = "未来5日上涨市" if mkt_dir == 'future_up' else "未来5日下跌市"
        logger.info(f"\n  【{label}】")
        env_df = df.filter(pl.col('future_market_dir') == mkt_dir)
        for window in [5, 20]:
            group_stats = env_df.filter(pl.col('beta_group').is_not_null()).group_by('beta_group').agg([
                pl.col(f'future_ret_{window}d').mean().alias('mean_ret'),
                pl.col(f'future_ret_{window}d').median().alias('median_ret'),
                pl.len().alias('count')
            ])
            for row in group_stats.sort('beta_group').iter_rows(named=True):
                logger.info(f"    {row['beta_group']:4s} Beta | {window}d: 均值={row['mean_ret']*100:6.2f}%, 中位数={row['median_ret']*100:6.2f}%, N={row['count']}")

def analyze_momentum_vs_beta(df):
    """2. 动量因子 vs Beta 独立性检验 - 简化版"""
    logger.info("\n" + "=" * 70)
    logger.info("分析2: 动量因子 vs Beta 独立性检验")
    logger.info("=" * 70)

    # 用过去20日收益作为动量
    df = df.with_columns(
        (pl.col('close') / pl.col('close').shift(20) - 1).alias('momentum_20d')
    )

    # 过滤极端值
    df_clean = df.filter(
        pl.col('momentum_20d').is_not_null() &
        pl.col('beta_60d').is_not_null() &
        pl.col('future_ret_5d').is_not_null() &
        (pl.col('future_ret_5d').abs() < 0.3) &
        (pl.col('momentum_20d').abs() < 0.5)
    )

    # 抽样：只保留最近6个月的数据做IC分析
    recent_date = df_clean['trade_date'].max()
    df_clean = df_clean.filter(
        pl.col('trade_date') >= '2025-01-01'
    )
    logger.info(f"  使用2025年以来数据: {len(df_clean)} 行")

    # IC对比
    logger.info("\n  IC对比:")
    daily_ic = []
    dates = df_clean['trade_date'].unique().sort().to_list()[:200]  # 限制天数
    for date in dates:
        day_df = df_clean.filter(pl.col('trade_date') == date)
        if len(day_df) > 50:
            for factor, col in [('Beta', 'beta_60d'), ('动量', 'momentum_20d')]:
                beta_arr = day_df[col].to_numpy().astype(float)
                ret_arr = day_df['future_ret_5d'].to_numpy().astype(float)
                valid = ~(np.isnan(beta_arr) | np.isnan(ret_arr))
                if valid.sum() > 30:
                    corr = np.corrcoef(beta_arr[valid], ret_arr[valid])[0, 1]
                    if not np.isnan(corr):
                        daily_ic.append({'factor': factor, 'ic': corr})

    if daily_ic:
        ic_df = pl.DataFrame(daily_ic)
        for factor in ['Beta', '动量']:
            fac_ic = ic_df.filter(pl.col('factor') == factor)
            if len(fac_ic) > 0:
                logger.info(f"    {factor}: IC均值={fac_ic['ic'].mean()*100:6.2f}%, IR={fac_ic['ic'].mean()/fac_ic['ic'].std():6.3f}, 正IC率={(fac_ic['ic']>0).mean()*100:5.1f}%")

def analyze_jensen_alpha(df):
    """3. Jensen's Alpha 分析 - 简化版"""
    logger.info("\n" + "=" * 70)
    logger.info("分析3: Jensen's Alpha 分析")
    logger.info("=" * 70)

    # 使用最近1年数据
    df_recent = df.filter(pl.col('trade_date') >= '2025-01-01')

    # 计算Alpha = 股票收益 - Beta * 市场收益
    # 用日频数据简单回归
    stock_stats = df_recent.group_by('stock_code').agg([
        pl.col('daily_return').mean().alias('avg_stock_ret'),
        pl.col('market_return').mean().alias('avg_market_ret'),
        pl.col('beta_60d').mean().alias('avg_beta')
    ])

    stock_stats = stock_stats.with_columns(
        (pl.col('avg_stock_ret') - pl.col('avg_beta') * pl.col('avg_market_ret')).alias('daily_alpha')
    )
    stock_stats = stock_stats.with_columns(
        (pl.col('daily_alpha') * 252).alias('annualized_alpha')
    )

    # Beta分组
    stock_stats = stock_stats.with_columns([
        pl.when(pl.col('avg_beta') < 0.8).then(pl.lit('low'))
        .when(pl.col('avg_beta') > 1.2).then(pl.lit('high'))
        .otherwise(pl.lit('mid'))
        .alias('beta_group')
    ])

    group_stats = stock_stats.group_by('beta_group').agg([
        pl.col('annualized_alpha').mean().alias('mean_alpha'),
        pl.col('annualized_alpha').median().alias('median_alpha'),
        pl.len().alias('count')
    ])

    logger.info("  Beta组别  年化Alpha均值  年化Alpha中位数  样本数")
    for row in group_stats.sort('beta_group').iter_rows(named=True):
        logger.info(f"    {row['beta_group']:4s}    {row['mean_alpha']*100:7.2f}%    {row['median_alpha']*100:7.2f}%    {row['count']}")

    high_alpha = group_stats.filter(pl.col('beta_group') == 'high')['mean_alpha'][0] if len(group_stats.filter(pl.col('beta_group') == 'high')) > 0 else 0
    low_alpha = group_stats.filter(pl.col('beta_group') == 'low')['mean_alpha'][0] if len(group_stats.filter(pl.col('beta_group') == 'low')) > 0 else 0

    logger.info("\n  结论: ", end="")
    if high_alpha > 0.02:
        logger.info("高Beta组Alpha为正，存在选股超额能力")
    elif high_alpha < -0.02:
        logger.info("高Beta组Alpha为负，超额收益完全来自市场暴露，无选股价值")
    else:
        logger.info("高Beta组Alpha接近零，超额收益基本来自市场暴露")

def analyze_time_stability(df):
    """4. 时间序列稳定性验证 - 简化版"""
    logger.info("\n" + "=" * 70)
    logger.info("分析4: 时间序列稳定性分段验证")
    logger.info("=" * 70)

    periods = [
        ('2020-2022', '2020-01-01', '2022-12-31'),
        ('2023-2024', '2023-01-01', '2024-12-31'),
        ('2025-2026', '2025-01-01', '2026-12-31'),
    ]

    for period_name, start, end in periods:
        logger.info(f"\n  【{period_name}】")
        period_df = df.filter(
            (pl.col('trade_date') >= start) & (pl.col('trade_date') <= end)
        )
        if len(period_df) < 1000:
            logger.info("    数据不足，跳过")
            continue

        # Beta分组
        stock_beta = period_df.group_by('stock_code').agg([
            pl.col('beta_60d').median().alias('median_beta')
        ])
        stock_beta = stock_beta.with_columns([
            pl.when(pl.col('median_beta') < 0.8).then(pl.lit('low'))
            .when(pl.col('median_beta') > 1.2).then(pl.lit('high'))
            .otherwise(pl.lit('mid'))
            .alias('beta_group')
        ])
        period_df = period_df.join(stock_beta.select(['stock_code', 'beta_group']), on='stock_code', how='left')

        for window in [20, 60]:
            group_stats = period_df.filter(pl.col('beta_group').is_not_null()).group_by('beta_group').agg([
                pl.col(f'future_ret_{window}d').mean().alias('mean_ret'),
                pl.len().alias('count')
            ])
            high_ret = 0
            low_ret = 0
            for row in group_stats.iter_rows(named=True):
                if row['beta_group'] == 'high':
                    high_ret = row['mean_ret']
                elif row['beta_group'] == 'low':
                    low_ret = row['mean_ret']
            diff = (high_ret - low_ret) * 100
            logger.info(f"    {window}d: 高Beta={high_ret*100:6.2f}%, 低Beta={low_ret*100:6.2f}%, 差异={diff:+.2f}%")

def main():
    logger.info("=" * 70)
    logger.info("深度验证: 高Beta与'好的更好'假说")
    logger.info("=" * 70)

    df = load_data()

    analyze_forward_market_direction(df)
    analyze_momentum_vs_beta(df)
    analyze_jensen_alpha(df)
    analyze_time_stability(df)

    logger.info("\n" + "=" * 70)
    logger.info("综合结论")
    logger.info("=" * 70)

if __name__ == '__main__':
    main()