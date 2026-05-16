#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
综合技术指标批量计算脚本
=========================
使用 Polars 高性能计算引擎，为 stock_daily.parquet 计算全面的量化指标。
时间范围：2020年1月1日 至最新数据

指标分类：
1. 动量类：RSI(6,12,24)、MACD、KDJ(9,3,3)、W%R(14)、CCI(14)
2. 趋势类：布林带(20,2)、DMI(14)、TRIX(12)
3. 能量/成交量类：OBV、VWAP、VR(26)、BIAS(6,12,24)
4. 波动率类：HV(20,60)、ATR(14)
5. 统计衍生指标：滚动收益率、滚动波动率、最大回撤、夏普比率、均线多头排列、金叉死叉

用法:
    python sandbox/compute_comprehensive_indicators.py
"""

import polars as pl
import os
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============
PARQUET_PATH = Path("data/parquet_data/stock_daily.parquet")
OUTPUT_PATH = Path("data/parquet_data/stock_daily_with_all_indicators.parquet")
START_DATE = "2020-01-01"  # 计算起始日期
# ==================================


def compute_rsi(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """
    计算 RSI (相对强弱指数)
    RSI = 100 - 100 / (1 + RS), RS = 平均涨幅 / 平均跌幅
    """
    return df.with_columns([
        (pl.col("close") - pl.col("prev_close")).alias("_price_diff")
    ]).with_columns([
        pl.when(pl.col("_price_diff") > 0).then(pl.col("_price_diff")).otherwise(0.0).alias("_gain"),
        pl.when(pl.col("_price_diff") < 0).then(-pl.col("_price_diff")).otherwise(0.0).alias("_loss")
    ]).with_columns([
        pl.col("_gain").ewm_mean(span=period).over("stock_code").alias("_avg_gain"),
        pl.col("_loss").ewm_mean(span=period).over("stock_code").alias("_avg_loss")
    ]).with_columns([
        (100 - 100 / (1 + pl.col("_avg_gain") / (pl.col("_avg_loss") + 1e-10))).alias(f"rsi_{period}")
    ]).drop(["_price_diff", "_gain", "_loss", "_avg_gain", "_avg_loss"])


def compute_macd(df: pl.LazyFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pl.LazyFrame:
    """
    计算 MACD 指标
    DIF = EMA(fast) - EMA(slow)
    DEA = EMA(signal) of DIF
    MACD_BAR = 2 * (DIF - DEA)
    """
    return df.with_columns([
        (pl.col("close").ewm_mean(span=fast).over("stock_code") -
         pl.col("close").ewm_mean(span=slow).over("stock_code")).alias("macd_dif")
    ]).with_columns([
        pl.col("macd_dif").ewm_mean(span=signal).over("stock_code").alias("macd_dea")
    ]).with_columns([
        (2 * (pl.col("macd_dif") - pl.col("macd_dea"))).alias("macd_bar")
    ])


def compute_kdj(df: pl.LazyFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pl.LazyFrame:
    """
    计算 KDJ 随机指标
    RSV = (close - low_n) / (high_n - low_n) * 100
    K = EMA(m1) of RSV
    D = EMA(m2) of K
    J = 3K - 2D
    """
    return df.with_columns([
        ((pl.col("close") - pl.col("low").rolling_min(window_size=n).over("stock_code")) /
         (pl.col("high").rolling_max(window_size=n).over("stock_code") -
          pl.col("low").rolling_min(window_size=n).over("stock_code") + 1e-10) * 100
        ).alias("_rsv")
    ]).with_columns([
        pl.col("_rsv").ewm_mean(span=m1).over("stock_code").alias("kdj_k")
    ]).with_columns([
        pl.col("kdj_k").ewm_mean(span=m2).over("stock_code").alias("kdj_d")
    ]).with_columns([
        (3 * pl.col("kdj_k") - 2 * pl.col("kdj_d")).alias("kdj_j")
    ]).drop("_rsv")


def compute_wr(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """
    计算威廉指标 W%R (Williams %R)
    W%R = (high_n - close) / (high_n - low_n) * -100
    值域: -100 到 0，-80以下超卖，-20以上超买
    """
    return df.with_columns([
        ((pl.col("high").rolling_max(window_size=period).over("stock_code") - pl.col("close")) /
         (pl.col("high").rolling_max(window_size=period).over("stock_code") -
          pl.col("low").rolling_min(window_size=period).over("stock_code") + 1e-10) * -100
        ).alias(f"wr_{period}")
    ])


def compute_cci(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """
    计算 CCI 顺势指标 (Commodity Channel Index)
    TP = (high + low + close) / 3
    CCI = (TP - MA(TP)) / (0.015 * MD)
    MD = 平均绝对偏差
    """
    return df.with_columns([
        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("_tp")
    ]).with_columns([
        pl.col("_tp").rolling_mean(window_size=period).over("stock_code").alias("_tp_ma")
    ]).with_columns([
        (pl.col("_tp") - pl.col("_tp_ma")).abs().rolling_mean(window_size=period).over("stock_code").alias("_md")
    ]).with_columns([
        ((pl.col("_tp") - pl.col("_tp_ma")) / (0.015 * (pl.col("_md") + 1e-10))).alias(f"cci_{period}")
    ]).drop(["_tp", "_tp_ma", "_md"])


def compute_bollinger(df: pl.LazyFrame, period: int = 20, std_dev: float = 2.0) -> pl.LazyFrame:
    """
    计算布林带 (Bollinger Bands)
    中轨 = MA(period)
    上轨 = 中轨 + std_dev * STD
    下轨 = 中轨 - std_dev * STD
    """
    return df.with_columns([
        pl.col("close").rolling_mean(window_size=period).over("stock_code").alias("boll_mid"),
        pl.col("close").rolling_std(window_size=period).over("stock_code").alias("_boll_std")
    ]).with_columns([
        (pl.col("boll_mid") + std_dev * pl.col("_boll_std")).alias("boll_upper"),
        (pl.col("boll_mid") - std_dev * pl.col("_boll_std")).alias("boll_lower")
    ]).drop("_boll_std")


def compute_dmi(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """
    计算 DMI 趋向指标 (Directional Movement Index)
    +DM = max(high - high_prev, 0) if high - high_prev > low_prev - low else 0
    -DM = max(low_prev - low, 0) if low_prev - low > high - high_prev else 0
    TR = max(high - low, |high - close_prev|, |low - close_prev|)
    +DI = 100 * EMA(+DM) / EMA(TR)
    -DI = 100 * EMA(-DM) / EMA(TR)
    DX = 100 * |+DI - -DI| / (+DI + -DI)
    ADX = EMA(DX)
    """
    return df.with_columns([
        (pl.col("high") - pl.col("high").shift(1).over("stock_code")).alias("_high_diff"),
        (pl.col("low").shift(1).over("stock_code") - pl.col("low")).alias("_low_diff")
    ]).with_columns([
        pl.when((pl.col("_high_diff") > pl.col("_low_diff")) & (pl.col("_high_diff") > 0))
          .then(pl.col("_high_diff")).otherwise(0.0).alias("_plus_dm"),
        pl.when((pl.col("_low_diff") > pl.col("_high_diff")) & (pl.col("_low_diff") > 0))
          .then(pl.col("_low_diff")).otherwise(0.0).alias("_minus_dm")
    ]).with_columns([
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("prev_close")).abs(),
            (pl.col("low") - pl.col("prev_close")).abs()
        ).alias("_tr")
    ]).with_columns([
        pl.col("_plus_dm").ewm_mean(span=period).over("stock_code").alias("_plus_dm_ema"),
        pl.col("_minus_dm").ewm_mean(span=period).over("stock_code").alias("_minus_dm_ema"),
        pl.col("_tr").ewm_mean(span=period).over("stock_code").alias("_tr_ema")
    ]).with_columns([
        (100 * pl.col("_plus_dm_ema") / (pl.col("_tr_ema") + 1e-10)).alias("dmi_pdi"),
        (100 * pl.col("_minus_dm_ema") / (pl.col("_tr_ema") + 1e-10)).alias("dmi_mdi")
    ]).with_columns([
        (100 * (pl.col("dmi_pdi") - pl.col("dmi_mdi")).abs() /
         (pl.col("dmi_pdi") + pl.col("dmi_mdi") + 1e-10)).alias("_dx")
    ]).with_columns([
        pl.col("_dx").ewm_mean(span=period).over("stock_code").alias("dmi_adx")
    ]).drop(["_high_diff", "_low_diff", "_plus_dm", "_minus_dm", "_tr",
             "_plus_dm_ema", "_minus_dm_ema", "_tr_ema", "_dx"])


def compute_trix(df: pl.LazyFrame, period: int = 12) -> pl.LazyFrame:
    """
    计算 TRIX 三重指数平滑平均线
    TRIX = EMA(EMA(EMA(close))) 的三重平滑
    这里简化为单重EMA的变化率版本
    """
    return df.with_columns([
        pl.col("close").ewm_mean(span=period).over("stock_code").alias("_ema1")
    ]).with_columns([
        pl.col("_ema1").ewm_mean(span=period).over("stock_code").alias("_ema2")
    ]).with_columns([
        pl.col("_ema2").ewm_mean(span=period).over("stock_code").alias("_ema3")
    ]).with_columns([
        ((pl.col("_ema3") - pl.col("_ema3").shift(1).over("stock_code")) /
         (pl.col("_ema3").shift(1).over("stock_code") + 1e-10) * 100).alias(f"trix_{period}")
    ]).drop(["_ema1", "_ema2", "_ema3"])


def compute_obv(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    计算 OBV 能量潮 (On Balance Volume)
    如果 close > close_prev: OBV = OBV_prev + volume
    如果 close < close_prev: OBV = OBV_prev - volume
    如果 close = close_prev: OBV = OBV_prev
    """
    return df.with_columns([
        pl.when(pl.col("close") > pl.col("prev_close")).then(pl.col("volume"))
          .when(pl.col("close") < pl.col("prev_close")).then(-pl.col("volume"))
          .otherwise(0).alias("_obv_change")
    ]).with_columns([
        pl.col("_obv_change").cum_sum().over("stock_code").alias("obv")
    ]).drop("_obv_change")


def compute_vwap(df: pl.LazyFrame, period: int = 20) -> pl.LazyFrame:
    """
    计算 VWAP 成交量加权平均价
    VWAP = Σ(typical_price * volume) / Σ(volume)
    typical_price = (high + low + close) / 3
    """
    return df.with_columns([
        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("_tp")
    ]).with_columns([
        (pl.col("_tp") * pl.col("volume")).alias("_tp_vol")
    ]).with_columns([
        (pl.col("_tp_vol").rolling_sum(window_size=period).over("stock_code") /
         (pl.col("volume").rolling_sum(window_size=period).over("stock_code") + 1e-10)).alias(f"vwap_{period}")
    ]).drop(["_tp", "_tp_vol"])


def compute_vr(df: pl.LazyFrame, period: int = 26) -> pl.LazyFrame:
    """
    计算 VR 成交量变异率 (Volume Ratio)
    VR = (上涨日成交量和 + 平盘日成交量和/2) / (下跌日成交量和 + 平盘日成交量和/2) * 100
    """
    return df.with_columns([
        pl.when(pl.col("close") > pl.col("prev_close")).then(pl.col("volume")).otherwise(0).alias("_up_vol"),
        pl.when(pl.col("close") < pl.col("prev_close")).then(pl.col("volume")).otherwise(0).alias("_down_vol"),
        pl.when(pl.col("close") == pl.col("prev_close")).then(pl.col("volume") / 2).otherwise(0).alias("_flat_vol")
    ]).with_columns([
        (pl.col("_up_vol").rolling_sum(window_size=period).over("stock_code") +
         pl.col("_flat_vol").rolling_sum(window_size=period).over("stock_code")).alias("_up_sum"),
        (pl.col("_down_vol").rolling_sum(window_size=period).over("stock_code") +
         pl.col("_flat_vol").rolling_sum(window_size=period).over("stock_code")).alias("_down_sum")
    ]).with_columns([
        ((pl.col("_up_sum") + 1e-10) / (pl.col("_down_sum") + 1e-10) * 100).alias(f"vr_{period}")
    ]).drop(["_up_vol", "_down_vol", "_flat_vol", "_up_sum", "_down_sum"])


def compute_bias(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """
    计算 BIAS 乖离率
    BIAS = (close - MA(period)) / MA(period) * 100
    """
    return df.with_columns([
        ((pl.col("close") - pl.col("close").rolling_mean(window_size=period).over("stock_code")) /
         (pl.col("close").rolling_mean(window_size=period).over("stock_code") + 1e-10) * 100).alias(f"bias_{period}")
    ])


def compute_atr(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """
    计算 ATR 真实波幅均值 (Average True Range)
    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = MA(TR)
    """
    return df.with_columns([
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("prev_close")).abs(),
            (pl.col("low") - pl.col("prev_close")).abs()
        ).alias("_tr")
    ]).with_columns([
        pl.col("_tr").rolling_mean(window_size=period).over("stock_code").alias(f"atr_{period}")
    ]).drop("_tr")


def compute_hv(df: pl.LazyFrame, period: int) -> pl.LazyFrame:
    """
    计算 HV 历史波动率 (Historical Volatility)
    基于对数收益率的年化标准差
    HV = STD(ln(close/close_prev)) * sqrt(252) * 100
    """
    return df.with_columns([
        ((pl.col("close") / (pl.col("prev_close") + 1e-10)).log()).alias("_log_ret")
    ]).with_columns([
        (pl.col("_log_ret").rolling_std(window_size=period).over("stock_code") *
         (252.0 ** 0.5) * 100).alias(f"hv_{period}d")
    ]).drop("_log_ret")


def compute_rolling_returns(df: pl.LazyFrame, periods: list) -> pl.LazyFrame:
    """
    计算滚动收益率
    ret_n = (close / close.shift(n) - 1) * 100
    """
    for p in periods:
        df = df.with_columns([
            ((pl.col("close") / (pl.col("close").shift(p).over("stock_code") + 1e-10) - 1) * 100).alias(f"ret_{p}d")
        ])
    return df


def compute_rolling_volatility(df: pl.LazyFrame, period: int = 20) -> pl.LazyFrame:
    """
    计算滚动波动率 (收益率标准差年化)
    """
    return df.with_columns([
        ((pl.col("close") / (pl.col("prev_close") + 1e-10) - 1).alias("_daily_ret"))
    ]).with_columns([
        (pl.col("_daily_ret").rolling_std(window_size=period).over("stock_code") *
         (252.0 ** 0.5) * 100).alias(f"volatility_{period}d")
    ]).drop("_daily_ret")


def compute_max_drawdown(df: pl.LazyFrame, period: int = 20) -> pl.LazyFrame:
    """
    计算滚动最大回撤
    max_drawdown = (close / rolling_max(close) - 1) * 100
    """
    return df.with_columns([
        pl.col("close").rolling_max(window_size=period).over("stock_code").alias("_rolling_high")
    ]).with_columns([
        ((pl.col("close") / (pl.col("_rolling_high") + 1e-10) - 1) * 100).alias(f"max_drawdown_{period}d")
    ]).drop("_rolling_high")


def compute_sharpe(df: pl.LazyFrame, period: int = 20, risk_free_rate: float = 0.03) -> pl.LazyFrame:
    """
    计算滚动夏普比率
    Sharpe = (mean(return) - risk_free) / std(return) * sqrt(252)
    """
    return df.with_columns([
        ((pl.col("close") / (pl.col("prev_close") + 1e-10) - 1).alias("_daily_ret"))
    ]).with_columns([
        pl.col("_daily_ret").rolling_mean(window_size=period).over("stock_code").alias("_mean_ret"),
        pl.col("_daily_ret").rolling_std(window_size=period).over("stock_code").alias("_std_ret")
    ]).with_columns([
        (((pl.col("_mean_ret") - risk_free_rate / 252) / (pl.col("_std_ret") + 1e-10)) * (252 ** 0.5)).alias(f"sharpe_{period}d")
    ]).drop(["_daily_ret", "_mean_ret", "_std_ret"])


def compute_ma_alignment(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    计算均线多头排列标记
    ma_bull = 1 if ma5 > ma10 > ma20 else 0
    """
    return df.with_columns([
        pl.when(
            (pl.col("ma5") > pl.col("ma10")) &
            (pl.col("ma10") > pl.col("ma20"))
        ).then(1).otherwise(0).alias("ma_bull_alignment")
    ])


def compute_golden_cross(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    计算金叉/死叉标记
    golden_cross = 1 if ma5 crosses above ma10
    death_cross = 1 if ma5 crosses below ma10
    """
    return df.with_columns([
        (pl.col("ma5") - pl.col("ma10")).alias("_ma_diff")
    ]).with_columns([
        pl.col("_ma_diff").shift(1).over("stock_code").alias("_ma_diff_prev")
    ]).with_columns([
        pl.when(
            (pl.col("_ma_diff") > 0) & (pl.col("_ma_diff_prev") <= 0)
        ).then(1).otherwise(0).alias("golden_cross"),
        pl.when(
            (pl.col("_ma_diff") < 0) & (pl.col("_ma_diff_prev") >= 0)
        ).then(1).otherwise(0).alias("death_cross")
    ]).drop(["_ma_diff", "_ma_diff_prev"])


def main():
    print("=" * 80)
    print("📊 综合技术指标批量计算工具")
    print("=" * 80)

    if not PARQUET_PATH.exists():
        print(f"❌ 错误: 找不到源文件 {PARQUET_PATH}")
        return

    print(f"📁 读取源文件: {PARQUET_PATH}")
    print(f"📅 计算时间范围: {START_DATE} 至今")
    start_time = datetime.now()

    # 使用 LazyFrame 进行延迟计算
    df = pl.scan_parquet(PARQUET_PATH)

    # 筛选2020年以后的数据
    df = df.filter(pl.col("trade_date") >= START_DATE)

    # 确保按股票和日期排序
    df = df.sort(["stock_code", "trade_date"])

    print("\n🔧 开始计算指标...")

    # ========== 1. 动量类指标 ==========
    print("\n📈 1. 动量类指标")

    print("   - RSI (6, 12, 24)")
    for period in [6, 12, 24]:
        df = compute_rsi(df, period)

    print("   - MACD (12, 26, 9)")
    df = compute_macd(df, fast=12, slow=26, signal=9)

    print("   - KDJ (9, 3, 3)")
    df = compute_kdj(df, n=9, m1=3, m2=3)

    print("   - W%R (14)")
    df = compute_wr(df, period=14)

    print("   - CCI (14)")
    df = compute_cci(df, period=14)

    # ========== 2. 趋势类指标 ==========
    print("\n📊 2. 趋势类指标")

    print("   - 布林带 (20, 2)")
    df = compute_bollinger(df, period=20, std_dev=2.0)

    print("   - DMI (14)")
    df = compute_dmi(df, period=14)

    print("   - TRIX (12)")
    df = compute_trix(df, period=12)

    # ========== 3. 能量/成交量类指标 ==========
    print("\n🔋 3. 能量/成交量类指标")

    print("   - OBV")
    df = compute_obv(df)

    print("   - VWAP (20)")
    df = compute_vwap(df, period=20)

    print("   - VR (26)")
    df = compute_vr(df, period=26)

    print("   - BIAS (6, 12, 24)")
    for period in [6, 12, 24]:
        df = compute_bias(df, period)

    # ========== 4. 波动率类指标 ==========
    print("\n📉 4. 波动率类指标")

    print("   - HV (20, 60)")
    for period in [20, 60]:
        df = compute_hv(df, period)

    print("   - ATR (14)")
    df = compute_atr(df, period=14)

    # ========== 5. 统计衍生指标 ==========
    print("\n📋 5. 统计衍生指标")

    print("   - 滚动收益率 (5, 20, 60)")
    df = compute_rolling_returns(df, periods=[5, 20, 60])

    print("   - 滚动波动率 (20)")
    df = compute_rolling_volatility(df, period=20)

    print("   - 最大回撤 (20)")
    df = compute_max_drawdown(df, period=20)

    print("   - 夏普比率 (20)")
    df = compute_sharpe(df, period=20, risk_free_rate=0.03)

    print("   - 均线多头排列")
    df = compute_ma_alignment(df)

    print("   - 金叉/死叉标记")
    df = compute_golden_cross(df)

    # 收集结果并写入
    print(f"\n💾 写入结果: {OUTPUT_PATH}")
    result = df.collect()
    result.write_parquet(OUTPUT_PATH)

    elapsed = (datetime.now() - start_time).total_seconds()

    # 统计新增列
    new_columns = [
        # 动量类
        "rsi_6", "rsi_12", "rsi_24",
        "macd_dif", "macd_dea", "macd_bar",
        "kdj_k", "kdj_d", "kdj_j",
        "wr_14", "cci_14",
        # 趋势类
        "boll_upper", "boll_mid", "boll_lower",
        "dmi_pdi", "dmi_mdi", "dmi_adx",
        "trix_12",
        # 能量类
        "obv", "vwap_20", "vr_26",
        "bias_6", "bias_12", "bias_24",
        # 波动率类
        "hv_20d", "hv_60d", "atr_14",
        # 统计衍生
        "ret_5d", "ret_20d", "ret_60d",
        "volatility_20d", "max_drawdown_20d", "sharpe_20d",
        "ma_bull_alignment", "golden_cross", "death_cross"
    ]

    print("\n" + "=" * 80)
    print(f"✅ 完成! 耗时: {elapsed:.2f} 秒")
    print(f"   总行数: {len(result):,}")
    print(f"   新增指标列: {len(new_columns)} 个")
    print("\n📋 新增指标列表:")
    print("   【动量类】")
    print("      RSI: rsi_6, rsi_12, rsi_24")
    print("      MACD: macd_dif, macd_dea, macd_bar")
    print("      KDJ: kdj_k, kdj_d, kdj_j")
    print("      W%R: wr_14")
    print("      CCI: cci_14")
    print("   【趋势类】")
    print("      布林带: boll_upper, boll_mid, boll_lower")
    print("      DMI: dmi_pdi, dmi_mdi, dmi_adx")
    print("      TRIX: trix_12")
    print("   【能量/成交量类】")
    print("      OBV, VWAP: obv, vwap_20")
    print("      VR: vr_26")
    print("      BIAS: bias_6, bias_12, bias_24")
    print("   【波动率类】")
    print("      HV: hv_20d, hv_60d")
    print("      ATR: atr_14")
    print("   【统计衍生】")
    print("      收益率: ret_5d, ret_20d, ret_60d")
    print("      风险指标: volatility_20d, max_drawdown_20d, sharpe_20d")
    print("      信号标记: ma_bull_alignment, golden_cross, death_cross")
    print(f"\n💾 输出文件: {OUTPUT_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
