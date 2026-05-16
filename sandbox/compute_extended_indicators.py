#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扩展技术指标与风险指标计算脚本
===============================
基于已有指标数据，添加：
1. EMA指标 (12, 26, 50, 200)
2. 市场风险指标 (Beta, Alpha, Correlation)
3. 风险调整指标 (Sortino, Calmar, VaR)
4. 技术指标补充 (MFI, Volume Std, BB Width, MACD Cross)
5. 多窗口滚动指标 (20/60/250日)

用法:
    python sandbox/compute_extended_indicators.py
"""

import polars as pl
import numpy as np
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============
INPUT_PATH = Path("data/parquet_data/stock_daily_with_all_indicators.parquet")
BENCHMARK_PATH = Path("data/parquet_data/benchmark_daily.parquet")
OUTPUT_PATH = Path("data/parquet_data/stock_daily_complete_indicators.parquet")
START_DATE = "2020-01-01"
BENCHMARK_CODE = "000300"  # 沪深300作为市场基准
# ==================================


def compute_ema(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """计算指数移动平均线 EMA"""
    return df.with_columns([
        pl.col("close").ewm_mean(span=period, adjust=False).over("stock_code").alias(f"ema{period}")
    ])


def compute_macd_cross(df: pl.LazyFrame) -> pl.LazyFrame:
    """计算MACD金叉/死叉标记"""
    return df.with_columns([
        (pl.col("macd_dif") - pl.col("macd_dea")).alias("_macd_diff")
    ]).with_columns([
        pl.col("_macd_diff").shift(1).over("stock_code").alias("_macd_diff_prev")
    ]).with_columns([
        pl.when(
            (pl.col("_macd_diff") > 0) & (pl.col("_macd_diff_prev") <= 0)
        ).then(1).otherwise(0).alias("macd_golden_cross"),
        pl.when(
            (pl.col("_macd_diff") < 0) & (pl.col("_macd_diff_prev") >= 0)
        ).then(1).otherwise(0).alias("macd_death_cross")
    ]).drop(["_macd_diff", "_macd_diff_prev"])


def compute_mfi(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """
    计算 MFI 资金流量指标 (Money Flow Index)
    类似RSI但结合成交量
    """
    return df.with_columns([
        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("_typical_price")
    ]).with_columns([
        (pl.col("_typical_price") * pl.col("volume")).alias("_raw_money_flow")
    ]).with_columns([
        pl.when(pl.col("_typical_price") > pl.col("_typical_price").shift(1).over("stock_code"))
          .then(pl.col("_raw_money_flow")).otherwise(0).alias("_positive_flow"),
        pl.when(pl.col("_typical_price") < pl.col("_typical_price").shift(1).over("stock_code"))
          .then(pl.col("_raw_money_flow")).otherwise(0).alias("_negative_flow")
    ]).with_columns([
        pl.col("_positive_flow").rolling_sum(window_size=period).over("stock_code").alias("_pos_sum"),
        pl.col("_negative_flow").rolling_sum(window_size=period).over("stock_code").alias("_neg_sum")
    ]).with_columns([
        (100 - (100 / (1 + pl.col("_pos_sum") / (pl.col("_neg_sum") + 1e-10)))).alias(f"mfi_{period}")
    ]).drop(["_typical_price", "_raw_money_flow", "_positive_flow", "_negative_flow", "_pos_sum", "_neg_sum"])


def compute_volume_std(df: pl.LazyFrame, period: int = 20) -> pl.LazyFrame:
    """计算成交量标准差"""
    return df.with_columns([
        pl.col("volume").rolling_std(window_size=period).over("stock_code").alias(f"volume_std_{period}d")
    ])


def compute_bb_width(df: pl.LazyFrame) -> pl.LazyFrame:
    """计算布林带宽度 (上轨-下轨)/中轨"""
    return df.with_columns([
        ((pl.col("boll_upper") - pl.col("boll_lower")) / (pl.col("boll_mid") + 1e-10) * 100).alias("bb_width_20")
    ])


def compute_atr_ratio(df: pl.LazyFrame, short_period: int = 14, long_period: int = 50) -> pl.LazyFrame:
    """计算ATR比例 ATR(14) / ATR(50)"""
    return df.with_columns([
        pl.col("close").shift(1).over("stock_code").alias("_prev_close")
    ]).with_columns([
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("_prev_close")).abs(),
            (pl.col("low") - pl.col("_prev_close")).abs()
        ).alias("_tr")
    ]).with_columns([
        pl.col("_tr").rolling_mean(window_size=short_period).over("stock_code").alias(f"_atr_{short_period}"),
        pl.col("_tr").rolling_mean(window_size=long_period).over("stock_code").alias(f"_atr_{long_period}")
    ]).with_columns([
        (pl.col(f"_atr_{short_period}") / (pl.col(f"_atr_{long_period}") + 1e-10)).alias(f"atr_ratio_{short_period}_{long_period}")
    ]).drop(["_prev_close", "_tr", f"_atr_{short_period}", f"_atr_{long_period}"])


def compute_rolling_beta_alpha(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """
    计算滚动Beta和Alpha
    使用线性回归: stock_return = alpha + beta * market_return
    这里使用简化公式计算
    """
    # 计算个股日收益率
    df = df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1)).alias("_stock_ret")
    ])

    # 计算滚动协方差和方差
    df = df.with_columns([
        pl.col("_stock_ret").rolling_mean(window_size=period).over("stock_code").alias("_stock_mean"),
        pl.col("market_return").rolling_mean(window_size=period).over("stock_code").alias("_market_mean")
    ])

    # Beta = Cov(stock, market) / Var(market)
    # 使用简化计算
    df = df.with_columns([
        ((pl.col("_stock_ret") - pl.col("_stock_mean")) *
         (pl.col("market_return") - pl.col("_market_mean"))).alias("_cov_term"),
        ((pl.col("market_return") - pl.col("_market_mean")) ** 2).alias("_var_term")
    ])

    df = df.with_columns([
        pl.col("_cov_term").rolling_sum(window_size=period).over("stock_code").alias("_cov_sum"),
        pl.col("_var_term").rolling_sum(window_size=period).over("stock_code").alias("_var_sum")
    ])

    df = df.with_columns([
        (pl.col("_cov_sum") / (pl.col("_var_sum") + 1e-10)).alias(f"beta_{period}d")
    ])

    # Alpha = mean(stock_return) - beta * mean(market_return)
    # 年化处理
    df = df.with_columns([
        ((pl.col("_stock_mean") - pl.col(f"beta_{period}d") * pl.col("_market_mean")) * 252 * 100).alias(f"alpha_{period}d")
    ])

    return df.drop(["_stock_ret", "_stock_mean", "_market_mean", "_cov_term", "_var_term", "_cov_sum", "_var_sum"])


def compute_rolling_correlation(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """计算滚动相关系数"""
    return df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1)).alias("_stock_ret")
    ]).with_columns([
        pl.col("_stock_ret").rolling_mean(window_size=period).over("stock_code").alias("_stock_mean"),
        pl.col("market_return").rolling_mean(window_size=period).over("stock_code").alias("_market_mean")
    ]).with_columns([
        ((pl.col("_stock_ret") - pl.col("_stock_mean")) *
         (pl.col("market_return") - pl.col("_market_mean"))).alias("_cov_term"),
        ((pl.col("_stock_ret") - pl.col("_stock_mean")) ** 2).alias("_stock_var"),
        ((pl.col("market_return") - pl.col("_market_mean")) ** 2).alias("_market_var")
    ]).with_columns([
        pl.col("_cov_term").rolling_sum(window_size=period).over("stock_code").alias("_cov_sum"),
        pl.col("_stock_var").rolling_sum(window_size=period).over("stock_code").alias("_stock_var_sum"),
        pl.col("_market_var").rolling_sum(window_size=period).over("stock_code").alias("_market_var_sum")
    ]).with_columns([
        (pl.col("_cov_sum") / ((pl.col("_stock_var_sum") * pl.col("_market_var_sum")).sqrt() + 1e-10)).alias(f"corr_{period}d")
    ]).drop(["_stock_ret", "_stock_mean", "_market_mean", "_cov_term", "_stock_var", "_market_var",
             "_cov_sum", "_stock_var_sum", "_market_var_sum"])


def compute_excess_return(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """计算累计超额收益"""
    df = df.with_columns([
        (pl.col("close") / (pl.col("close").shift(period).over("stock_code") + 1e-10) - 1).alias("_stock_ret_period"),
        (pl.col("market_close") / (pl.col("market_close").shift(period).over("stock_code") + 1e-10) - 1).alias("_market_ret_period")
    ])
    return df.with_columns([
        (pl.col("_stock_ret_period") - pl.col("_market_ret_period")).alias(f"excess_ret_{period}d")
    ]).drop(["_stock_ret_period", "_market_ret_period"])


def compute_information_ratio(df: pl.LazyFrame, period: int = 250) -> pl.LazyFrame:
    """
    计算信息比率 (Information Ratio)
    IR = 年化超额收益 / 跟踪误差
    """
    return df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1) - pl.col("market_return")).alias("_active_ret")
    ]).with_columns([
        pl.col("_active_ret").rolling_mean(window_size=period).over("stock_code").alias("_active_mean"),
        pl.col("_active_ret").rolling_std(window_size=period).over("stock_code").alias("_tracking_error")
    ]).with_columns([
        ((pl.col("_active_mean") * 252) / (pl.col("_tracking_error") * (252 ** 0.5) + 1e-10)).alias(f"ir_{period}d")
    ]).drop(["_active_ret", "_active_mean", "_tracking_error"])


def compute_sortino_ratio(df: pl.LazyFrame, period: int = 250) -> pl.LazyFrame:
    """
    计算Sortino比率 (只考虑下行风险)
    Sortino = (年化收益 - 无风险利率) / 下行波动率
    """
    risk_free_daily = 0.03 / 252  # 假设3%年化无风险利率

    return df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1)).alias("_daily_ret")
    ]).with_columns([
        pl.col("_daily_ret").rolling_mean(window_size=period).over("stock_code").alias("_mean_ret")
    ]).with_columns([
        # 只保留负收益
        pl.when(pl.col("_daily_ret") < 0).then(pl.col("_daily_ret") ** 2).otherwise(0).alias("_downside_sq")
    ]).with_columns([
        (pl.col("_downside_sq").rolling_sum(window_size=period).over("stock_code") / period).sqrt().alias("_downside_std")
    ]).with_columns([
        (((pl.col("_mean_ret") - risk_free_daily) / (pl.col("_downside_std") + 1e-10)) * (252 ** 0.5)).alias(f"sortino_{period}d")
    ]).drop(["_daily_ret", "_mean_ret", "_downside_sq", "_downside_std"])


def compute_calmar_ratio(df: pl.LazyFrame, period: int = 250) -> pl.LazyFrame:
    """
    计算Calmar比率
    Calmar = 年化收益 / 最大回撤
    """
    return df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1)).alias("_daily_ret")
    ]).with_columns([
        pl.col("_daily_ret").rolling_mean(window_size=period).over("stock_code").alias("_mean_ret")
    ]).with_columns([
        pl.col("close").rolling_max(window_size=period).over("stock_code").alias("_rolling_high")
    ]).with_columns([
        ((pl.col("close") / (pl.col("_rolling_high") + 1e-10) - 1)).alias("_drawdown")
    ]).with_columns([
        pl.col("_drawdown").rolling_min(window_size=period).over("stock_code").alias("_max_dd")
    ]).with_columns([
        ((pl.col("_mean_ret") * 252) / (pl.col("_max_dd").abs() + 1e-10)).alias(f"calmar_{period}d")
    ]).drop(["_daily_ret", "_mean_ret", "_rolling_high", "_drawdown", "_max_dd"])


def compute_var(df: pl.LazyFrame, period: int = 250, confidence: float = 0.95) -> pl.LazyFrame:
    """
    计算VaR (在险价值)
    使用历史模拟法，取指定置信水平的分位数
    """
    # 注意：Polars不直接支持rolling quantile with custom percentile
    # 这里使用近似方法
    return df.with_columns([
        ((pl.col("close") / pl.col("prev_close") - 1) * 100).alias("_daily_ret_pct")
    ]).with_columns([
        pl.col("_daily_ret_pct").rolling_mean(window_size=period).over("stock_code").alias("_mean_ret"),
        pl.col("_daily_ret_pct").rolling_std(window_size=period).over("stock_code").alias("_std_ret")
    ]).with_columns([
        # 使用正态分布近似: VaR = mean - z_score * std
        # 95%置信度对应z=1.645
        (pl.col("_mean_ret") - 1.645 * pl.col("_std_ret")).alias(f"var_95_{period}d")
    ]).drop(["_daily_ret_pct", "_mean_ret", "_std_ret"])


def load_benchmark_data() -> pl.DataFrame:
    """加载基准指数数据"""
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"基准数据文件不存在: {BENCHMARK_PATH}")

    # 加载基准数据
    bench = pl.scan_parquet(BENCHMARK_PATH)

    # 标准化指数代码 (去除.SZ/.SH后缀)
    bench = bench.with_columns([
        pl.col("code").str.replace(r"\.SZ$", "").str.replace(r"\.SH$", "").alias("benchmark_code")
    ])

    # 筛选沪深300
    bench = bench.filter(pl.col("benchmark_code") == BENCHMARK_CODE)

    # 重命名列避免冲突
    bench = bench.rename({
        "close": "market_close",
        "date": "trade_date"
    })

    # 计算市场收益率
    bench = bench.with_columns([
        ((pl.col("market_close") / pl.col("market_close").shift(1) - 1)).alias("market_return")
    ])

    return bench.select(["trade_date", "market_close", "market_return"]).collect()


def main():
    print("=" * 80)
    print("📊 扩展技术指标与风险指标计算工具")
    print("=" * 80)

    if not INPUT_PATH.exists():
        print(f"❌ 错误: 找不到输入文件 {INPUT_PATH}")
        return

    print(f"📁 读取输入文件: {INPUT_PATH}")
    print(f"📅 计算时间范围: {START_DATE} 至今")
    start_time = datetime.now()

    # 加载基准数据
    print("\n📈 加载基准指数数据...")
    try:
        benchmark_df = load_benchmark_data()
        print(f"   基准指数: 沪深300 ({BENCHMARK_CODE})")
        print(f"   基准数据行数: {len(benchmark_df):,}")
    except Exception as e:
        print(f"❌ 加载基准数据失败: {e}")
        return

    # 加载股票数据
    df = pl.scan_parquet(INPUT_PATH)

    # 筛选2020年以后的数据
    df = df.filter(pl.col("trade_date") >= START_DATE)

    # 确保按股票和日期排序
    df = df.sort(["stock_code", "trade_date"])

    # 转换为 eager DataFrame 进行 join
    df_stock = df.collect()

    # Join 基准数据
    print("   Join 基准数据...")
    df_merged = df_stock.join(benchmark_df, on="trade_date", how="left")

    # 转回 lazy
    df = df_merged.lazy()

    print("\n🔧 开始计算扩展指标...")

    # ========== 1. EMA指标 ==========
    print("\n📈 1. EMA指标")
    for period in [12, 26, 50, 200]:
        print(f"   - EMA{period}")
        df = compute_ema(df, period)

    # ========== 2. 技术指标补充 ==========
    print("\n📊 2. 技术指标补充")

    print("   - MACD金叉/死叉")
    df = compute_macd_cross(df)

    print("   - MFI (14)")
    df = compute_mfi(df, period=14)

    print("   - 成交量标准差 (20)")
    df = compute_volume_std(df, period=20)

    print("   - 布林带宽度")
    df = compute_bb_width(df)

    print("   - ATR比例 (14/50)")
    df = compute_atr_ratio(df, short_period=14, long_period=50)

    # ========== 3. 市场风险指标 ==========
    print("\n📉 3. 市场风险指标 (需要基准数据)")

    for period in [60, 120, 250]:
        print(f"   - Beta/Alpha/Corr ({period}日)")
        df = compute_rolling_beta_alpha(df, period)
        df = compute_rolling_correlation(df, period)

    print("   - 超额收益 (20日)")
    df = compute_excess_return(df, period=20)

    print("   - 信息比率 (250日)")
    df = compute_information_ratio(df, period=250)

    # ========== 4. 风险调整指标 ==========
    print("\n🔒 4. 风险调整指标")

    print("   - Sortino比率 (250日)")
    df = compute_sortino_ratio(df, period=250)

    print("   - Calmar比率 (250日)")
    df = compute_calmar_ratio(df, period=250)

    print("   - VaR 95% (250日)")
    df = compute_var(df, period=250, confidence=0.95)

    # ========== 5. 多窗口滚动指标 ==========
    print("\n📋 5. 多窗口滚动指标")

    print("   - 最大回撤 (60日, 250日)")
    # 20日已在之前计算
    for period in [60, 250]:
        df = df.with_columns([
            pl.col("close").rolling_max(window_size=period).over("stock_code").alias("_rolling_high")
        ]).with_columns([
            ((pl.col("close") / (pl.col("_rolling_high") + 1e-10) - 1) * 100).alias(f"max_drawdown_{period}d")
        ]).drop("_rolling_high")

    # 收集结果并写入
    print(f"\n💾 写入结果: {OUTPUT_PATH}")
    result = df.collect()
    result.write_parquet(OUTPUT_PATH)

    elapsed = (datetime.now() - start_time).total_seconds()

    # 统计新增列
    new_columns = [
        # EMA
        "ema12", "ema26", "ema50", "ema200",
        # 技术指标补充
        "macd_golden_cross", "macd_death_cross", "mfi_14", "volume_std_20d", "bb_width_20", "atr_ratio_14_50",
        # 市场风险
        "beta_60d", "beta_120d", "beta_250d",
        "alpha_60d", "alpha_120d", "alpha_250d",
        "corr_60d", "corr_120d", "corr_250d",
        "excess_ret_20d", "ir_250d",
        # 风险调整
        "sortino_250d", "calmar_250d", "var_95_250d",
        # 多窗口回撤
        "max_drawdown_60d", "max_drawdown_250d"
    ]

    print("\n" + "=" * 80)
    print(f"✅ 完成! 耗时: {elapsed:.2f} 秒")
    print(f"   总行数: {len(result):,}")
    print(f"   新增指标列: {len(new_columns)} 个")
    print("\n📋 新增指标列表:")
    print("   【EMA指标】")
    print("      ema12, ema26, ema50, ema200")
    print("   【技术指标补充】")
    print("      MACD信号: macd_golden_cross, macd_death_cross")
    print("      MFI: mfi_14")
    print("      成交量: volume_std_20d")
    print("      布林带: bb_width_20")
    print("      ATR: atr_ratio_14_50")
    print("   【市场风险指标】")
    print("      Beta: beta_60d, beta_120d, beta_250d")
    print("      Alpha: alpha_60d, alpha_120d, alpha_250d")
    print("      相关系数: corr_60d, corr_120d, corr_250d")
    print("      超额收益: excess_ret_20d")
    print("      信息比率: ir_250d")
    print("   【风险调整指标】")
    print("      Sortino: sortino_250d")
    print("      Calmar: calmar_250d")
    print("      VaR: var_95_250d")
    print("   【多窗口回撤】")
    print("      max_drawdown_60d, max_drawdown_250d")
    print(f"\n💾 输出文件: {OUTPUT_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
