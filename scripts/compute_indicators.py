"""
技术指标批量计算脚本
====================
使用 Polars 高性能计算引擎，为 stock_daily.parquet 补全常用量化指标。

新增指标列表:
- RSI (14日相对强弱指数)
- KDJ (随机指标: K, D, J)
- ATR (14日真实波幅均值)
- MACD (DIF, DEA, MACD柱)
- 布林带 (BOLL_UPPER, BOLL_MID, BOLL_LOWER)
- 长周期均线 (MA60, MA120, MA250)
- 乖离率 (BIAS_5, BIAS_10, BIAS_20)

用法:
    python scripts/compute_indicators.py
"""

import polars as pl
import os
from datetime import datetime

# ============== 配置 ==============
PARQUET_PATH = r"d:\aquatrade\data\parquet_data\stock_daily.parquet"
OUTPUT_PATH = r"d:\aquatrade\data\parquet_data\stock_daily_with_indicators.parquet"
# ==================================


def compute_rsi(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """计算 RSI (相对强弱指数) - 使用原生 Polars 表达式"""
    return df.with_columns([
        # 计算涨跌差值
        (pl.col("close") - pl.col("prev_close")).alias("_price_diff")
    ]).with_columns([
        # 上涨幅度 (正值保留，负值变0)
        pl.when(pl.col("_price_diff") > 0)
          .then(pl.col("_price_diff"))
          .otherwise(0.0)
          .alias("_gain"),
        # 下跌幅度 (负值取绝对值，正值变0)
        pl.when(pl.col("_price_diff") < 0)
          .then(-pl.col("_price_diff"))
          .otherwise(0.0)
          .alias("_loss")
    ]).with_columns([
        # 计算平均涨幅和平均跌幅 (使用 EWM 更接近经典 RSI)
        pl.col("_gain").ewm_mean(span=period).over("stock_code").alias("_avg_gain"),
        pl.col("_loss").ewm_mean(span=period).over("stock_code").alias("_avg_loss")
    ]).with_columns([
        # RSI = 100 - 100 / (1 + RS)
        (100 - 100 / (1 + pl.col("_avg_gain") / (pl.col("_avg_loss") + 1e-10))).alias(f"rsi_{period}")
    ]).drop(["_price_diff", "_gain", "_loss", "_avg_gain", "_avg_loss"])


def compute_kdj(df: pl.LazyFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pl.LazyFrame:
    """计算 KDJ 随机指标"""
    return df.with_columns([
        # 计算 RSV
        ((pl.col("close") - pl.col("low").rolling_min(window_size=n).over("stock_code")) /
         (pl.col("high").rolling_max(window_size=n).over("stock_code") - 
          pl.col("low").rolling_min(window_size=n).over("stock_code") + 1e-10) * 100
        ).alias("rsv")
    ]).with_columns([
        # K = 2/3 * 前K + 1/3 * RSV (简化为 EMA)
        pl.col("rsv").ewm_mean(span=m1).over("stock_code").alias("kdj_k")
    ]).with_columns([
        # D = 2/3 * 前D + 1/3 * K
        pl.col("kdj_k").ewm_mean(span=m2).over("stock_code").alias("kdj_d")
    ]).with_columns([
        # J = 3K - 2D
        (3 * pl.col("kdj_k") - 2 * pl.col("kdj_d")).alias("kdj_j")
    ]).drop("rsv")


def compute_atr(df: pl.LazyFrame, period: int = 14) -> pl.LazyFrame:
    """计算 ATR (真实波幅均值)"""
    return df.with_columns([
        # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("prev_close")).abs(),
            (pl.col("low") - pl.col("prev_close")).abs()
        ).alias("tr")
    ]).with_columns([
        pl.col("tr").rolling_mean(window_size=period).over("stock_code").alias(f"atr_{period}")
    ]).drop("tr")


def compute_macd(df: pl.LazyFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pl.LazyFrame:
    """计算 MACD 指标"""
    return df.with_columns([
        # DIF = EMA12 - EMA26
        (pl.col("close").ewm_mean(span=fast).over("stock_code") - 
         pl.col("close").ewm_mean(span=slow).over("stock_code")).alias("macd_dif")
    ]).with_columns([
        # DEA = DIF 的 9日 EMA
        pl.col("macd_dif").ewm_mean(span=signal).over("stock_code").alias("macd_dea")
    ]).with_columns([
        # MACD 柱 = 2 * (DIF - DEA)
        (2 * (pl.col("macd_dif") - pl.col("macd_dea"))).alias("macd_histogram")
    ])


def compute_bollinger(df: pl.LazyFrame, period: int = 20, std_dev: float = 2.0) -> pl.LazyFrame:
    """计算布林带"""
    return df.with_columns([
        pl.col("close").rolling_mean(window_size=period).over("stock_code").alias("boll_mid"),
        pl.col("close").rolling_std(window_size=period).over("stock_code").alias("boll_std")
    ]).with_columns([
        (pl.col("boll_mid") + std_dev * pl.col("boll_std")).alias("boll_upper"),
        (pl.col("boll_mid") - std_dev * pl.col("boll_std")).alias("boll_lower")
    ]).drop("boll_std")


def compute_long_ma(df: pl.LazyFrame) -> pl.LazyFrame:
    """计算长周期均线 MA60, MA120, MA250"""
    return df.with_columns([
        pl.col("close").rolling_mean(window_size=60).over("stock_code").alias("ma60"),
        pl.col("close").rolling_mean(window_size=120).over("stock_code").alias("ma120"),
        pl.col("close").rolling_mean(window_size=250).over("stock_code").alias("ma250"),
    ])


def compute_bias(df: pl.LazyFrame) -> pl.LazyFrame:
    """计算乖离率 BIAS"""
    return df.with_columns([
        ((pl.col("close") - pl.col("ma5")) / (pl.col("ma5") + 1e-10) * 100).alias("bias_5"),
        ((pl.col("close") - pl.col("ma10")) / (pl.col("ma10") + 1e-10) * 100).alias("bias_10"),
        ((pl.col("close") - pl.col("ma20")) / (pl.col("ma20") + 1e-10) * 100).alias("bias_20"),
    ])


def main():
    print("=" * 60)
    print("📊 技术指标批量计算工具")
    print("=" * 60)
    
    if not os.path.exists(PARQUET_PATH):
        print(f"❌ 错误: 找不到源文件 {PARQUET_PATH}")
        return
    
    print(f"📁 读取源文件: {PARQUET_PATH}")
    start_time = datetime.now()
    
    # 使用 LazyFrame 进行延迟计算
    df = pl.scan_parquet(PARQUET_PATH)
    
    # 确保按股票和日期排序
    df = df.sort(["stock_code", "trade_date"])
    
    print("🔧 计算指标中...")
    
    # 依次计算各指标
    print("   - RSI (14日)")
    df = compute_rsi(df)
    
    print("   - KDJ (随机指标)")
    df = compute_kdj(df)
    
    print("   - ATR (真实波幅)")
    df = compute_atr(df)
    
    print("   - MACD")
    df = compute_macd(df)
    
    print("   - 布林带")
    df = compute_bollinger(df)
    
    print("   - 长周期均线 (MA60/120/250)")
    df = compute_long_ma(df)
    
    print("   - 乖离率 (BIAS)")
    df = compute_bias(df)
    
    # 收集结果并写入
    print(f"💾 写入结果: {OUTPUT_PATH}")
    result = df.collect()
    result.write_parquet(OUTPUT_PATH)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print("=" * 60)
    print(f"✅ 完成! 耗时: {elapsed:.2f} 秒")
    print(f"   新增列: rsi_14, kdj_k, kdj_d, kdj_j, atr_14,")
    print(f"          macd_dif, macd_dea, macd_histogram,")
    print(f"          boll_upper, boll_mid, boll_lower,")
    print(f"          ma60, ma120, ma250, bias_5, bias_10, bias_20")
    print(f"   输出文件: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
