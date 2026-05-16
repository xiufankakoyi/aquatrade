"""
验证假设：高Beta股票是否收益更好（好的更好，坏的更坏）

研究问题：
1. 高Beta股票的未来收益是否显著高于低Beta股票？
2. 上涨市场中高Beta是否表现更好？
3. 下跌市场中高Beta是否跌得更多？
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np
from loguru import logger
from datetime import datetime

def analyze_beta_vs_future_return():
    logger.info("=" * 70)
    logger.info("Beta vs 未来收益 分析")
    logger.info("=" * 70)

    # 加载因子数据
    logger.info("加载因子数据...")
    factors_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "factors_momentum_hot.parquet")
    logger.info(f"  因子数据: {factors_df.shape[0]} 行, 日期范围: {factors_df['trade_date'].min()} ~ {factors_df['trade_date'].max()}")

    # 加载股票日线数据（计算未来收益）
    logger.info("加载日线数据...")
    daily_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "stock_daily.parquet")
    logger.info(f"  日线数据: {daily_df.shape[0]} 行")

    # 只保留需要的列
    daily_df = daily_df.select(['trade_date', 'stock_code', 'close', 'prev_close'])

    # 计算日收益率
    daily_df = daily_df.with_columns([
        ((pl.col('close') / pl.col('prev_close') - 1)).alias('daily_return')
    ])

    # 只保留2020年后的数据（因子数据从这时候开始比较完整）
    factors_df = factors_df.filter(pl.col('trade_date') >= pl.date(2020, 1, 1))

    # 合并因子和收益数据
    logger.info("合并数据...")

    # 统一日期类型
    if factors_df['trade_date'].dtype == pl.Date:
        factors_df = factors_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))
    if daily_df['trade_date'].dtype == pl.Date:
        daily_df = daily_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))

    df = factors_df.join(daily_df, on=['trade_date', 'stock_code'], how='left')

    # 计算未来N日收益（未来5日、20日、60日）
    logger.info("计算未来收益...")
    df = df.sort(['stock_code', 'trade_date'])

    for window in [5, 20, 60]:
        df = df.with_columns(
            (pl.col('close').shift(-window) / pl.col('close') - 1).alias(f'future_ret_{window}d')
        )

    # 只保留有Beta数据的记录
    df = df.filter(pl.col('beta_60d').is_not_null())

    logger.info(f"合并后数据: {df.shape[0]} 行")

    # 合并后数据: 2070727 行

    # ===============================
    # 分析1: 按Beta十分位分组，看未来收益
    # ===============================
    logger.info("\n" + "=" * 70)
    logger.info("分析1: Beta十分位 vs 未来收益")
    logger.info("=" * 70)

    # 获取最新日期的Beta来分组（避免未来信息泄露）
    # 实际上应该用滚动窗口，但这里简化处理
    latest_factors = factors_df.filter(pl.col('trade_date') >= '2024-01-01')
    latest_factors = latest_factors.group_by('stock_code').agg([
        pl.col('beta_60d').mean().alias('avg_beta_60d')
    ])

    # 分成十组
    latest_factors = latest_factors.sort('avg_beta_60d')
    latest_factors = latest_factors.with_columns(
        (pl.arange(0, pl.len()) / pl.len() * 10 + 1).floor().alias('beta_decile')
    )

    beta_dist = latest_factors.group_by('beta_decile').agg([
        pl.col('avg_beta_60d').mean().alias('avg_beta'),
        pl.col('stock_code').count().alias('count')
    ])
    logger.info(f"Beta分组分布:\n{beta_dist}")

    # ===============================
    # 分析2: 不同Beta水平下的平均收益
    # ===============================
    logger.info("\n" + "=" * 70)
    logger.info("分析2: 高/中/低Beta组未来收益对比")
    logger.info("=" * 70)

    # 用历史Beta中位数来分组
    stock_beta = factors_df.group_by('stock_code').agg([
        pl.col('beta_60d').median().alias('median_beta')
    ])

    # 低Beta: < 0.8, 中Beta: 0.8~1.2, 高Beta: > 1.2
    stock_beta = stock_beta.with_columns([
        pl.when(pl.col('median_beta') < 0.8).then(pl.lit('low'))
        .when(pl.col('median_beta') > 1.2).then(pl.lit('high'))
        .otherwise(pl.lit('mid'))
        .alias('beta_group')
    ])

    # 合并到主数据
    df = df.join(stock_beta.select(['stock_code', 'beta_group', 'median_beta']), on='stock_code', how='left')

    # 计算每个Beta组的平均未来收益
    for window in [5, 20, 60]:
        group_stats = df.filter(pl.col('beta_group').is_not_null()).group_by('beta_group').agg([
            pl.col(f'future_ret_{window}d').mean().alias(f'mean_future_ret_{window}d'),
            pl.col(f'future_ret_{window}d').median().alias(f'median_future_ret_{window}d'),
            pl.col(f'future_ret_{window}d').std().alias(f'std_future_ret_{window}d'),
            pl.count().alias('count')
        ])
        logger.info(f"\n  {window}日未来收益:")
        for row in group_stats.iter_rows(named=True):
            logger.info(f"    {row['beta_group']:4s}: 均值={row[f'mean_future_ret_{window}d']*100:6.2f}%, 中位数={row[f'median_future_ret_{window}d']*100:6.2f}%, 标准差={row[f'std_future_ret_{window}d']*100:6.2f}%, N={row['count']}")

    # ===============================
    # 分析3: 分市场环境
    # ===============================
    logger.info("\n" + "=" * 70)
    logger.info("分析3: 不同市场环境下高/低Beta表现")
    logger.info("=" * 70)

    # 计算市场收益率（用全体股票加权平均）
    market_ret = df.group_by('trade_date').agg([
        (pl.col('daily_return') * pl.col('close')).sum() / pl.col('close').sum()  # 加权平均
    ]).rename({'daily_return': 'market_return'})

    df = df.join(market_ret, on='trade_date', how='left')

    # 分上涨/下跌市场
    df = df.with_columns([
        pl.when(pl.col('market_return') > 0).then(pl.lit('up'))
        .otherwise(pl.lit('down'))
        .alias('market_env')
    ])

    # 分组统计
    for env in ['up', 'down']:
        logger.info(f"\n  市场环境: {'上涨' if env == 'up' else '下跌'}")
        env_df = df.filter(pl.col('market_env') == env)
        for window in [5, 20]:
            group_stats = env_df.filter(pl.col('beta_group').is_not_null()).group_by('beta_group').agg([
                pl.col(f'future_ret_{window}d').mean().alias(f'mean_ret'),
                pl.count().alias('count')
            ])
            for row in group_stats.iter_rows(named=True):
                logger.info(f"    {row['beta_group']:4s} Beta | {window}d收益: {row['mean_ret']*100:6.2f}% (N={row['count']})")

    # ===============================
    # 分析4: Beta的预测能力统计
    # ===============================
    logger.info("\n" + "=" * 70)
    logger.info("分析4: Beta对未来收益的预测能力（IC/RankIC）")
    logger.info("=" * 70)

    # 计算日度IC
    daily_ic = []
    dates = df['trade_date'].unique().sort().to_list()
    for date in dates:
        day_df = df.filter(pl.col('trade_date') == date)
        if len(day_df) > 30 and 'future_ret_5d' in day_df.columns:
            # 过滤极端值
            day_df = day_df.filter(
                pl.col('beta_60d').is_not_null() &
                pl.col('future_ret_5d').is_not_null() &
                (pl.col('future_ret_5d').abs() < 0.3)  # 剔除涨跌停
            )
            if len(day_df) > 30:
                beta_arr = day_df['beta_60d'].to_numpy().astype(float)
                ret_arr = day_df['future_ret_5d'].to_numpy().astype(float)
                # 过滤NaN
                valid = ~(np.isnan(beta_arr) | np.isnan(ret_arr))
                if valid.sum() > 30:
                    corr = np.corrcoef(beta_arr[valid], ret_arr[valid])[0, 1]
                    if not np.isnan(corr):
                        daily_ic.append({'date': date, 'ic': corr})

    if daily_ic:
        ic_df = pl.DataFrame(daily_ic)
        logger.info(f"  Beta_60d vs Future_Ret_5d:")
        logger.info(f"    IC均值:   {ic_df['ic'].mean()*100:6.2f}%")
        logger.info(f"    IC标准差: {ic_df['ic'].std()*100:6.2f}%")
        logger.info(f"    IC_IR:    {ic_df['ic'].mean() / ic_df['ic'].std():6.2f}")
        logger.info(f"    IC>0比例: {(ic_df['ic'] > 0).mean()*100:6.2f}%")

        # 60日IC
        ic_df_60 = ic_df.with_columns([
            pl.col('ic').rolling_mean(window_size=60).alias('ic_60d')
        ])
        logger.info(f"    60日滚动IC均值: {ic_df_60['ic_60d'].mean()*100:6.2f}%")

    # ===============================
    # 结论
    # ===============================
    logger.info("\n" + "=" * 70)
    logger.info("结论")
    logger.info("=" * 70)

    # 综合判断
    if daily_ic:
        avg_ic = ic_df['ic'].mean()
        positive_ratio = (ic_df['ic'] > 0).mean()
        ir = avg_ic / ic_df['ic'].std()

        if avg_ic > 0.01 and positive_ratio > 0.55:
            conclusion = "高Beta → 未来收益更高（支持假设）"
        elif avg_ic < -0.01 and positive_ratio < 0.45:
            conclusion = "高Beta → 未来收益更低（反向假设）"
        else:
            conclusion = "Beta对未来收益无显著预测能力（不支持假设）"

        logger.info(f"  {conclusion}")
        logger.info(f"  IC={avg_ic*100:.3f}%, IR={ir:.3f}, 正IC比例={positive_ratio*100:.1f}%")

if __name__ == '__main__':
    analyze_beta_vs_future_return()