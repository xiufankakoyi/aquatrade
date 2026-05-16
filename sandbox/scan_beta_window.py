"""
Beta窗口扫描分析 - 纯Polars表达式版
利用协方差公式分解: β = [E(Ri·Rm) - E(Ri)E(Rm)] / [E(Rm²) - E(Rm)²]
所有期望值都用rolling_mean计算，无Python循环
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np
from loguru import logger
import time

WINDOWS = [3, 5, 7, 10, 15, 30]

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

def compute_beta_polars(df, window):
    w = window
    eps = 1e-10

    df = df.with_columns([
        (pl.col('daily_return') * pl.col('market_return')).alias('ret_product'),
        (pl.col('market_return') ** 2).alias('mkt_sq'),
    ])

    E_Ri_Rm = pl.col('ret_product').rolling_mean(window_size=w, min_samples=w).over('stock_code')
    E_Ri = pl.col('daily_return').rolling_mean(window_size=w, min_samples=w).over('stock_code')
    E_Rm = pl.col('market_return').rolling_mean(window_size=w, min_samples=w).over('stock_code')
    E_Rm_sq = pl.col('mkt_sq').rolling_mean(window_size=w, min_samples=w).over('stock_code')

    cov_numerator = E_Ri_Rm - E_Ri * E_Rm
    var_denominator = E_Rm_sq - E_Rm ** 2

    beta = (cov_numerator / (var_denominator + eps)).clip(-5, 5).alias(f'beta_{w}d')

    df = df.with_columns(beta)
    df = df.drop(['ret_product', 'mkt_sq'])

    return df

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

def analyze_window(df, window):
    beta_col = f'beta_{window}d'
    results = {'window': window}

    df_win = df.filter(pl.col('trade_date') >= '2023-01-01')
    df_win = df_win.filter(pl.col(beta_col).is_not_null())

    if len(df_win) < 3000:
        logger.warning(f"窗口{window}数据不足: {len(df_win)}")
        return None

    stock_beta = df_win.group_by('stock_code').agg([
        pl.col(beta_col).median().alias('median_beta')
    ])
    stock_beta = stock_beta.with_columns([
        pl.when(pl.col('median_beta') < 0.7).then(pl.lit('low'))
        .when(pl.col('median_beta') > 1.3).then(pl.lit('high'))
        .otherwise(pl.lit('mid'))
        .alias('beta_group')
    ])
    df_win = df_win.join(stock_beta.select(['stock_code', 'beta_group']), on='stock_code', how='left')
    df_win = df_win.filter(pl.col('beta_group').is_not_null())

    daily_ic = []
    dates = df_win['trade_date'].unique().sort().to_list()[:300]
    for date in dates:
        day_df = df_win.filter(pl.col('trade_date') == date)
        if len(day_df) > 50:
            beta_arr = day_df[beta_col].to_numpy().astype(float)
            ret_arr = day_df['future_ret_5d'].to_numpy().astype(float)
            valid = ~(np.isnan(beta_arr) | np.isnan(ret_arr) | np.isinf(beta_arr) | np.isinf(ret_arr))
            if valid.sum() > 30:
                corr = np.corrcoef(beta_arr[valid], ret_arr[valid])[0, 1]
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

    group_stats = df_win.group_by('beta_group').agg([
        pl.col('future_ret_5d').mean().alias('mean_ret_5d'),
        pl.col('future_ret_20d').mean().alias('mean_ret_20d'),
    ])
    for row in group_stats.iter_rows(named=True):
        g = row['beta_group']
        results[f'{g}_ret_5d'] = row['mean_ret_5d']
        results[f'{g}_ret_20d'] = row['mean_ret_20d']

    results['high_low_diff_5d'] = results.get('high_ret_5d', 0) - results.get('low_ret_5d', 0)
    results['high_low_diff_20d'] = results.get('high_ret_20d', 0) - results.get('low_ret_20d', 0)

    down_df = df_win.filter(pl.col('future_market_dir') == 'down')
    if len(down_df) > 500:
        down_group = down_df.group_by('beta_group').agg([
            pl.col('future_ret_5d').mean().alias('mean_ret'),
        ])
        for row in down_group.iter_rows(named=True):
            results[f"down_{row['beta_group']}_ret_5d"] = row['mean_ret']
        results['down_high_low_diff'] = results.get('down_high_ret_5d', 0) - results.get('down_low_ret_5d', 0)
    else:
        results['down_high_low_diff'] = None

    stock_stats = df_win.group_by('stock_code').agg([
        pl.col('daily_return').mean().alias('avg_ret'),
        pl.col('market_return').mean().alias('avg_mkt'),
        pl.col(beta_col).mean().alias('avg_beta')
    ])
    stock_stats = stock_stats.filter(pl.col('avg_beta').abs() < 10)
    stock_stats = stock_stats.with_columns(
        (pl.col('avg_ret') - pl.col('avg_beta') * pl.col('avg_mkt')).alias('daily_alpha')
    )
    stock_stats = stock_stats.with_columns(
        (pl.col('daily_alpha') * 252).alias('annual_alpha')
    )
    stock_stats = stock_stats.with_columns([
        pl.when(pl.col('avg_beta') < 0.7).then(pl.lit('low'))
        .when(pl.col('avg_beta') > 1.3).then(pl.lit('high'))
        .otherwise(pl.lit('mid'))
        .alias('beta_group')
    ])
    alpha_group = stock_stats.group_by('beta_group').agg([
        pl.col('annual_alpha').mean().alias('mean_alpha')
    ])
    for row in alpha_group.iter_rows(named=True):
        results[f"{row['beta_group']}_alpha"] = row['mean_alpha']

    results['high_low_alpha_diff'] = results.get('high_alpha', 0) - results.get('low_alpha', 0)

    return results

def main():
    t0 = time.time()
    logger.info("=" * 80)
    logger.info("Beta窗口扫描分析 - 纯Polars表达式版 (近3年)")
    logger.info("=" * 80)

    df = load_data()
    df = compute_market_return(df)

    logger.info("计算各窗口Beta (纯Polars rolling表达式)...")
    for w in WINDOWS:
        t1 = time.time()
        df = compute_beta_polars(df, w)
        logger.info(f"  {w}日 Beta完成 ({time.time()-t1:.1f}s)")

    df = add_future_vars(df)
    df = df.filter(
        (pl.col('daily_return').abs() < 0.3) &
        (pl.col('future_ret_5d').abs() < 0.3)
    )
    logger.info(f"数据准备完成: {df.shape[0]} 行")

    all_results = []
    for w in WINDOWS:
        logger.info(f"\n>>> 分析窗口: {w}日")
        t1 = time.time()
        result = analyze_window(df, w)
        if result:
            all_results.append(result)
            down_str = f"{result['down_high_low_diff']*100:+.2f}%" if result['down_high_low_diff'] is not None else "N/A"
            logger.info(f"    {time.time()-t1:.1f}s | IC={result['ic_mean']*100:.2f}%, IR={result['ic_ir']:.3f}, 正IC率={result['ic_positive_rate']*100:.1f}% | 高-低20d={result['high_low_diff_20d']*100:.2f}% | 下跌高-低={down_str} | Alpha高低差={result['high_low_alpha_diff']*100:.2f}%")

    logger.info("\n" + "=" * 80)
    logger.info("结果汇总")
    logger.info("=" * 80)

    header = f"{'窗口':^6} | {'IC均值':^8} | {'IC_IR':^8} | {'正IC率':^8} | {'高-低20d差':^10} | {'下跌高-低差':^12} | {'Alpha高低差':^10}"
    print(f"\n{header}")
    print("-" * 90)
    for r in sorted(all_results, key=lambda x: x['window']):
        down_str = f"{r['down_high_low_diff']*100:+.2f}%" if r['down_high_low_diff'] is not None else "     N/A    "
        print(f"{r['window']:^6} | {r['ic_mean']*100:^7.2f}% | {r['ic_ir']:^8.3f} | {r['ic_positive_rate']*100:^7.1f}% | {r['high_low_diff_20d']*100:^9.2f}% | {down_str:^12} | {r['high_low_alpha_diff']*100:^9.2f}%")

    if not all_results:
        return

    logger.info("\n" + "=" * 80)
    logger.info("关键发现")
    logger.info("=" * 80)

    best_ir = max(all_results, key=lambda x: x['ic_ir'])
    logger.info(f"\n1. IC_IR最优: {best_ir['window']}日 (IR={best_ir['ic_ir']:.3f})")

    best_alpha = max(all_results, key=lambda x: x['high_low_alpha_diff'])
    logger.info(f"2. Alpha差最优: {best_alpha['window']}日 (差值={best_alpha['high_low_alpha_diff']*100:.2f}%)")

    pos_alpha = [r for r in all_results if r.get('high_alpha', -999) > 0]
    if pos_alpha:
        logger.info(f"3. 高Beta Alpha转正窗口: {', '.join([str(r['window'])+'日' for r in pos_alpha])}")
    else:
        logger.info("3. 无任何窗口的高Beta Alpha转正")

    down_valid = [r for r in all_results if r['down_high_low_diff'] is not None and r['down_high_low_diff'] > 0]
    if down_valid:
        best_down = max(down_valid, key=lambda x: x['down_high_low_diff'])
        logger.info(f"4. 下跌市场超额最优: {best_down['window']}日 (高-低差={best_down['down_high_low_diff']*100:.2f}%)")
        logger.info("   → 高Beta在下跌市场中仍能贡献正超额")
    else:
        logger.info("4. 无任何窗口在下跌市场中实现高Beta超额为正")

    ic_sig = [r for r in all_results if r['ic_ir'] > 0.3 and r['ic_positive_rate'] > 0.55]
    if ic_sig:
        logger.info(f"5. IC显著为正的窗口: {', '.join([str(r['window'])+'日' for r in ic_sig])}")
    else:
        logger.info("5. 无任何窗口IC显著为正")

    logger.info(f"\n总耗时: {time.time()-t0:.1f}秒")

if __name__ == '__main__':
    main()