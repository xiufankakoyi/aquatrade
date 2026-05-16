"""
NAR (净涨跌不对称收益) & Capture Ratio 分析
与Beta窗口扫描相同的分析框架

NAR = mean(Ri|Rm>0) + mean(Ri|Rm<0)
Up Capture = mean(Ri|Rm>0) / mean(Rm|Rm>0)
Down Capture = mean(Ri|Rm<0) / mean(Rm|Rm<0)
Capture Ratio = Up Capture / Down Capture
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np
from loguru import logger
import time

WINDOWS = [10, 20, 30]

def load_data():
    logger.info("加载数据...")
    factors_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "factors_momentum_hot.parquet")
    daily_df = pl.read_parquet(BASE_DIR / "data" / "parquet_data" / "stock_daily.parquet")

    daily_df = daily_df.select(['trade_date', 'stock_code', 'close', 'prev_close'])
    daily_df = daily_df.with_columns([
        ((pl.col('close') / pl.col('prev_close') - 1)).alias('daily_return')
    ])

    if factors_df['trade_date'].dtype == pl.Date:
        factors_df = factors_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))
    if daily_df['trade_date'].dtype == pl.Date:
        daily_df = daily_df.with_columns(pl.col('trade_date').cast(pl.String).alias('trade_date'))

    df = factors_df.join(daily_df, on=['trade_date', 'stock_code'], how='left')
    df = df.sort(['stock_code', 'trade_date'])
    return df

def compute_market_return(df):
    market_ret = df.group_by('trade_date').agg([
        (pl.col('daily_return') * pl.col('close')).sum() / pl.col('close').sum()
    ]).rename({'daily_return': 'market_return'})
    df = df.join(market_ret, on='trade_date', how='left')
    return df

def calc_capture_metrics(group: pl.DataFrame, windows: list[int]):
    ret = group["daily_return"].to_numpy().astype(float)
    bench = group["market_return"].to_numpy().astype(float)
    n = len(ret)
    res = {}

    for w in windows:
        nar = np.full(n, np.nan)
        up_cap = np.full(n, np.nan)
        down_cap = np.full(n, np.nan)

        for i in range(w - 1, n):
            win_ret = ret[i - w + 1:i + 1]
            win_bench = bench[i - w + 1:i + 1]

            up_mask = win_bench > 0
            down_mask = win_bench < 0

            if up_mask.sum() >= 2 and down_mask.sum() >= 2:
                up_mean_ret = win_ret[up_mask].mean()
                down_mean_ret = win_ret[down_mask].mean()

                nar[i] = up_mean_ret + down_mean_ret

                up_mean_bench = win_bench[up_mask].mean()
                down_mean_bench = win_bench[down_mask].mean()

                if abs(up_mean_bench) > 1e-10:
                    up_cap[i] = up_mean_ret / up_mean_bench
                if abs(down_mean_bench) > 1e-10:
                    down_cap[i] = down_mean_ret / down_mean_bench

        res[f"NAR_{w}d"] = nar
        res[f"UpCapt_{w}d"] = up_cap
        res[f"DownCapt_{w}d"] = down_cap
        res[f"CaptRatio_{w}d"] = np.where(
            (np.isnan(down_cap)) | (down_cap == 0) | (np.isinf(down_cap)),
            np.nan,
            up_cap / down_cap
        )

    return group.with_columns([pl.Series(k, v) for k, v in res.items()])

def add_future_vars(df):
    df = df.sort('trade_date')
    df = df.with_columns(
        pl.col('market_return').shift(-5).over('stock_code').alias('future_market_ret_5d')
    )
    df = df.with_columns([
        pl.when(pl.col('future_market_ret_5d') > 0).then(pl.lit('up'))
        .otherwise(pl.lit('down'))
        .alias('future_market_dir')
    ])
    for w in [5, 20]:
        df = df.with_columns(
            (pl.col('close').shift(-w).over('stock_code') / pl.col('close') - 1).alias(f'future_ret_{w}d')
        )
    return df

def analyze_metric(df, metric_col, future_col='future_ret_5d', label="指标"):
    results = {'metric': label, 'col': metric_col}

    df_m = df.filter(pl.col('trade_date') >= '2023-01-01')
    df_m = df_m.filter(pl.col(metric_col).is_not_null())

    if len(df_m) < 3000:
        logger.warning(f"{label} 数据不足: {len(df_m)}")
        return None

    stock_metric = df_m.group_by('stock_code').agg([
        pl.col(metric_col).median().alias('median_val')
    ])
    stock_metric = stock_metric.with_columns([
        pl.when(pl.col('median_val') < pl.col('median_val').quantile(0.2))
        .then(pl.lit('Q1_low'))
        .when(pl.col('median_val') > pl.col('median_val').quantile(0.8))
        .then(pl.lit('Q5_high'))
        .otherwise(pl.lit('mid'))
        .alias('group')
    ])

    df_m = df_m.join(stock_metric.select(['stock_code', 'group']), on='stock_code', how='left')
    df_m = df_m.filter(pl.col('group').is_not_null())

    daily_ic = []
    dates = df_m['trade_date'].unique().sort().to_list()[:300]
    for date in dates:
        day_df = df_m.filter(pl.col('trade_date') == date)
        if len(day_df) > 50:
            val_arr = day_df[metric_col].to_numpy().astype(float)
            ret_arr = day_df[future_col].to_numpy().astype(float)
            valid = ~(np.isnan(val_arr) | np.isnan(ret_arr) | np.isinf(val_arr) | np.isinf(ret_arr))
            if valid.sum() > 30:
                corr = np.corrcoef(val_arr[valid], ret_arr[valid])[0, 1]
                if not np.isnan(corr):
                    daily_ic.append(corr)

    if daily_ic:
        ic_arr = np.array(daily_ic)
        results['ic_mean'] = np.mean(ic_arr)
        results['ic_std'] = np.std(ic_arr)
        results['ic_ir'] = np.mean(ic_arr) / np.std(ic_arr) if np.std(ic_arr) > 0 else 0
        results['ic_positive_rate'] = np.mean(ic_arr > 0)
    else:
        results['ic_mean'] = 0
        results['ic_std'] = 0
        results['ic_ir'] = 0
        results['ic_positive_rate'] = 0.5

    group_stats = df_m.group_by('group').agg([
        pl.col(future_col).mean().alias('mean_ret_5d'),
        pl.col('future_ret_20d').mean().alias('mean_ret_20d'),
        pl.len().alias('count')
    ])
    for row in group_stats.iter_rows(named=True):
        g = row['group']
        results[f'{g}_ret_5d'] = row['mean_ret_5d']
        results[f'{g}_ret_20d'] = row['mean_ret_20d']

    results['high_low_diff_5d'] = results.get('Q5_high_ret_5d', 0) - results.get('Q1_low_ret_5d', 0)
    results['high_low_diff_20d'] = results.get('Q5_high_ret_20d', 0) - results.get('Q1_low_ret_20d', 0)

    down_df = df_m.filter(pl.col('future_market_dir') == 'down')
    if len(down_df) > 500:
        down_group = down_df.group_by('group').agg([
            pl.col(future_col).mean().alias('mean_ret'),
        ])
        for row in down_group.iter_rows(named=True):
            results[f"down_{row['group']}_ret_5d"] = row['mean_ret']
        results['down_high_low_diff'] = results.get('down_Q5_high_ret_5d', 0) - results.get('down_Q1_low_ret_5d', 0)
    else:
        results['down_high_low_diff'] = None

    up_df = df_m.filter(pl.col('future_market_dir') == 'up')
    if len(up_df) > 500:
        up_group = up_df.group_by('group').agg([
            pl.col(future_col).mean().alias('mean_ret'),
        ])
        for row in up_group.iter_rows(named=True):
            results[f"up_{row['group']}_ret_5d"] = row['mean_ret']
        results['up_high_low_diff'] = results.get('up_Q5_high_ret_5d', 0) - results.get('up_Q1_low_ret_5d', 0)
    else:
        results['up_high_low_diff'] = None

    stock_stats = df_m.group_by('stock_code').agg([
        pl.col('daily_return').mean().alias('avg_ret'),
        pl.col('market_return').mean().alias('avg_mkt'),
        pl.col(metric_col).mean().alias('avg_metric')
    ])
    stock_stats = stock_stats.filter(
        pl.col('avg_metric').is_not_null(),
        pl.col('avg_metric').abs() < 100
    )
    stock_stats = stock_stats.with_columns(
        (pl.col('avg_ret') - pl.col('avg_mkt')).alias('daily_alpha')
    )
    stock_stats = stock_stats.with_columns(
        (pl.col('daily_alpha') * 252).alias('annual_alpha')
    )
    stock_stats = stock_stats.with_columns([
        pl.when(pl.col('avg_metric') < pl.col('avg_metric').quantile(0.2))
        .then(pl.lit('Q1_low'))
        .when(pl.col('avg_metric') > pl.col('avg_metric').quantile(0.8))
        .then(pl.lit('Q5_high'))
        .otherwise(pl.lit('mid'))
        .alias('group')
    ])
    alpha_group = stock_stats.group_by('group').agg([
        pl.col('annual_alpha').mean().alias('mean_alpha')
    ])
    for row in alpha_group.iter_rows(named=True):
        results[f"{row['group']}_alpha"] = row['mean_alpha']

    results['high_low_alpha_diff'] = results.get('Q5_high_alpha', 0) - results.get('Q1_low_alpha', 0)

    return results

def main():
    t0 = time.time()
    logger.info("=" * 80)
    logger.info("NAR & Capture Ratio 分析 (近3年)")
    logger.info("=" * 80)

    df = load_data()
    df = compute_market_return(df)

    logger.info("计算NAR和Capture Ratio (map_groups + NumPy)...")
    t1 = time.time()
    df = (
        df.sort(['stock_code', 'trade_date'])
        .group_by('stock_code', maintain_order=True)
        .map_groups(lambda g: calc_capture_metrics(g, WINDOWS))
    )
    logger.info(f"  计算完成 ({time.time()-t1:.1f}s)")

    df = add_future_vars(df)
    df = df.filter(
        (pl.col('daily_return').abs() < 0.3) &
        (pl.col('future_ret_5d').abs() < 0.3)
    )
    logger.info(f"数据准备完成: {df.shape[0]} 行")

    metrics = []
    for w in WINDOWS:
        for metric, label in [
            (f'NAR_{w}d', f'NAR_{w}d'),
            (f'CaptRatio_{w}d', f'CaptureRatio_{w}d'),
        ]:
            logger.info(f"\n>>> 分析 {label}")
            t2 = time.time()
            result = analyze_metric(df, metric, 'future_ret_5d', label)
            if result:
                metrics.append(result)
                down_str = f"{result['down_high_low_diff']*100:+.2f}%" if result['down_high_low_diff'] is not None else "N/A"
                up_str = f"{result['up_high_low_diff']*100:+.2f}%" if result.get('up_high_low_diff') is not None else "N/A"
                alpha_str = f"{result['high_low_alpha_diff']*100:+.2f}%"
                logger.info(f"    {time.time()-t2:.1f}s | IC={result['ic_mean']*100:.2f}%, IR={result['ic_ir']:.3f}, 正IC率={result['ic_positive_rate']*100:.1f}% | 高-低20d={result['high_low_diff_20d']*100:.2f}% | 上涨高-低={up_str} | 下跌高-低={down_str} | Alpha高低差={alpha_str}")

    logger.info("\n" + "=" * 80)
    logger.info("结果汇总")
    logger.info("=" * 80)

    header = f"{'指标':^18} | {'IC均值':^8} | {'IC_IR':^8} | {'正IC率':^8} | {'高-低20d差':^10} | {'上涨高-低差':^10} | {'下跌高-低差':^10} | {'Alpha高低差':^10}"
    print(f"\n{header}")
    print("-" * 110)
    for r in sorted(metrics, key=lambda x: (x['metric'], -x['ic_ir'])):
        down_str = f"{r['down_high_low_diff']*100:+.2f}%" if r['down_high_low_diff'] is not None else "     N/A"
        up_str = f"{r['up_high_low_diff']*100:+.2f}%" if r.get('up_high_low_diff') is not None else "     N/A"
        print(f"{r['metric']:^18} | {r['ic_mean']*100:^7.2f}% | {r['ic_ir']:^8.3f} | {r['ic_positive_rate']*100:^7.1f}% | {r['high_low_diff_20d']*100:^9.2f}% | {up_str:^10} | {down_str:^10} | {r['high_low_alpha_diff']*100:^9.2f}%")

    logger.info("\n" + "=" * 80)
    logger.info("关键发现")
    logger.info("=" * 80)

    if not metrics:
        return

    best_ic = max(metrics, key=lambda x: x['ic_ir'])
    logger.info(f"\n1. IC_IR最优: {best_ic['metric']} (IR={best_ic['ic_ir']:.3f})")

    best_alpha = max(metrics, key=lambda x: x['high_low_alpha_diff'])
    logger.info(f"2. Alpha差最优: {best_alpha['metric']} (差值={best_alpha['high_low_alpha_diff']*100:.2f}%)")

    nar_metrics = [m for m in metrics if 'NAR' in m['metric']]
    capt_metrics = [m for m in metrics if 'Capt' in m['metric']]

    logger.info(f"\n3. NAR指标表现:")
    for m in sorted(nar_metrics, key=lambda x: x['ic_ir'], reverse=True):
        logger.info(f"   {m['metric']}: IC={m['ic_mean']*100:.2f}%, IR={m['ic_ir']:.3f}, Alpha差={m['high_low_alpha_diff']*100:.2f}%")

    logger.info(f"\n4. Capture Ratio指标表现:")
    for m in sorted(capt_metrics, key=lambda x: x['ic_ir'], reverse=True):
        logger.info(f"   {m['metric']}: IC={m['ic_mean']*100:.2f}%, IR={m['ic_ir']:.3f}, Alpha差={m['high_low_alpha_diff']*100:.2f}%")

    pos_alpha = [m for m in metrics if m.get('Q5_high_alpha', -999) > 0]
    if pos_alpha:
        logger.info(f"\n5. Q5高分组Alpha转正: {', '.join([m['metric'] for m in pos_alpha])}")
    else:
        logger.info("\n5. 无任何指标的Q5高分组Alpha转正")

    down_valid = [m for m in metrics if m['down_high_low_diff'] is not None and m['down_high_low_diff'] > 0]
    if down_valid:
        best_down = max(down_valid, key=lambda x: x['down_high_low_diff'])
        logger.info(f"\n6. 下跌市场超额最优: {best_down['metric']} (高-低差={best_down['down_high_low_diff']*100:.2f}%)")
        logger.info("   → 高NAR/Capture组在下跌市场中仍能贡献正超额（真正的龙头多一条命）")
    else:
        logger.info("\n6. 无任何指标在下跌市场中实现高分组超额为正")

    logger.info(f"\n总耗时: {time.time()-t0:.1f}秒")

if __name__ == '__main__':
    main()