"""
箱体震荡 + MA10支撑 + 突破选股脚本

形态特征：
1. 箱体震荡：价格在一定区间内波动
2. 跌到但不跌破MA10：收盘价触及或接近MA10，但第二天反弹（支撑有效）
3. 刚突破箱体：最近突破了震荡区间上沿
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from data_svc.storage.lancedb_reader import LanceDBDataReader


def calculate_ma(close: np.ndarray, window: int = 10) -> np.ndarray:
    """计算移动平均线"""
    ma = np.full_like(close, np.nan)
    for i in range(window - 1, len(close)):
        ma[i] = np.mean(close[i - window + 1 : i + 1])
    return ma


def detect_box_oscillation(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    window: int = 20,
    oscillation_threshold: float = 0.15,
) -> tuple[bool, float, float]:
    """
    检测箱体震荡

    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        window: 检测窗口
        oscillation_threshold: 震荡幅度阈值（相对于价格的比例）

    Returns:
        (是否震荡, 箱体下沿, 箱体上沿)
    """
    if len(close) < window:
        return False, 0, 0

    recent_high = high[-window:]
    recent_low = low[-window:]
    recent_close = close[-window:]

    box_high = np.max(recent_high)
    box_low = np.min(recent_low)
    mid_price = np.mean(recent_close)

    amplitude = (box_high - box_low) / mid_price

    if amplitude < oscillation_threshold:
        return True, box_low, box_high

    return False, box_low, box_high


def check_ma10_support(
    close: np.ndarray,
    ma10: np.ndarray,
    lookback: int = 20,
    touch_threshold: float = 0.02,
) -> tuple[bool, int]:
    """
    检查MA10支撑有效性

    条件：
    1. 收盘价跌到MA10附近（差距小于touch_threshold）
    2. 第二天反弹（收盘价上涨）

    Args:
        close: 收盘价数组
        ma10: MA10数组
        lookback: 回看天数
        touch_threshold: 触及MA10的阈值（相对比例）

    Returns:
        (是否满足条件, 触及次数)
    """
    if len(close) < lookback + 1:
        return False, 0

    touch_count = 0
    valid_support = False

    for i in range(-lookback, -1):
        if np.isnan(ma10[i]):
            continue

        distance = (close[i] - ma10[i]) / ma10[i]

        if distance <= touch_threshold and distance >= -touch_threshold:
            touch_count += 1
            if close[i + 1] > close[i]:
                valid_support = True

    return valid_support, touch_count


def check_breakout(
    close: np.ndarray,
    high: np.ndarray,
    box_high: float,
    lookback: int = 5,
) -> tuple[bool, float]:
    """
    检查是否突破箱体

    Args:
        close: 收盘价数组
        high: 最高价数组
        box_high: 箱体上沿
        lookback: 回看天数

    Returns:
        (是否突破, 突破幅度)
    """
    if len(close) < lookback:
        return False, 0

    recent_close = close[-lookback:]
    recent_high = high[-lookback:]

    if np.max(recent_high) > box_high:
        breakout_pct = (recent_close[-1] - box_high) / box_high
        return True, breakout_pct

    return False, 0


def screen_stocks(
    reader: LanceDBDataReader,
    days: int = 60,
    box_window: int = 20,
    oscillation_threshold: float = 0.20,
    ma10_touch_threshold: float = 0.03,
    min_touch_count: int = 1,
) -> list[dict]:
    """
    筛选符合条件的股票

    Args:
        reader: 数据读取器
        days: 查询天数
        box_window: 箱体检测窗口
        oscillation_threshold: 震荡幅度阈值
        ma10_touch_threshold: MA10触及阈值
        min_touch_count: 最小触及次数

    Returns:
        符合条件的股票列表
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")

    logger.info(f"读取数据: {start_date} ~ {end_date}")

    df = reader.read(
        None,
        start_date=start_date,
        end_date=end_date,
        fields=["stock_code", "trade_date", "open", "high", "low", "close", "volume"],
    )

    if df.is_empty():
        logger.warning("没有读取到数据")
        return []

    logger.info(f"读取到 {len(df)} 条数据")

    df = df.sort(["stock_code", "trade_date"])

    results = []
    symbols = df["stock_code"].unique().to_list()
    logger.info(f"共 {len(symbols)} 只股票")

    stats = {
        "total": 0,
        "oscillating": 0,
        "has_support": 0,
        "breakout": 0,
    }

    for symbol in symbols:
        try:
            stock_df = df.filter(pl.col("stock_code") == symbol).sort("trade_date")

            if len(stock_df) < days:
                continue

            stats["total"] += 1

            close = stock_df["close"].cast(pl.Float64).to_numpy()[-days:]
            high = stock_df["high"].cast(pl.Float64).to_numpy()[-days:]
            low = stock_df["low"].cast(pl.Float64).to_numpy()[-days:]
            volume = stock_df["volume"].cast(pl.Float64).to_numpy()[-days:]
            dates = stock_df["trade_date"].to_numpy()[-days:]

            if np.isnan(close).any():
                continue

            ma10 = calculate_ma(close, 10)

            is_oscillating, box_low, box_high = detect_box_oscillation(
                high[:-5], low[:-5], close[:-5], box_window, oscillation_threshold
            )

            if not is_oscillating:
                continue

            stats["oscillating"] += 1

            has_support, touch_count = check_ma10_support(
                close[:-1], ma10[:-1], lookback=box_window, touch_threshold=ma10_touch_threshold
            )

            if not has_support or touch_count < min_touch_count:
                continue

            stats["has_support"] += 1

            is_breakout, breakout_pct = check_breakout(close, high, box_high, lookback=5)

            if not is_breakout:
                continue

            # 过滤掉突破幅度异常大的（可能是数据问题或已经大涨）
            if breakout_pct > 0.15:  # 突破幅度超过15%的跳过
                continue

            stats["breakout"] += 1

            results.append({
                "stock_code": symbol,
                "latest_date": str(dates[-1]),
                "latest_close": float(close[-1]),
                "box_high": float(box_high),
                "box_low": float(box_low),
                "box_amplitude": float((box_high - box_low) / np.mean(close)),
                "breakout_pct": float(breakout_pct),
                "ma10_touch_count": touch_count,
                "volume_ratio": float(volume[-1] / np.mean(volume[-box_window:]) if np.mean(volume[-box_window:]) > 0 else 0),
            })

        except Exception as e:
            logger.debug(f"处理 {symbol} 时出错: {e}")
            continue

    logger.info(f"筛选统计: 总计={stats['total']}, 震荡={stats['oscillating']}, 支撑={stats['has_support']}, 突破={stats['breakout']}")

    results.sort(key=lambda x: abs(x["breakout_pct"] - 0.05))  # 按5%突破幅度排序

    return results


def main():
    logger.info("开始筛选箱体震荡+MA10支撑+突破股票...")

    reader = LanceDBDataReader()

    results = screen_stocks(
        reader,
        days=40,
        box_window=15,
        oscillation_threshold=0.20,
        ma10_touch_threshold=0.03,
        min_touch_count=1,
    )

    logger.info(f"\n找到 {len(results)} 只符合条件的股票:\n")

    for i, r in enumerate(results[:20], 1):
        logger.info(
            f"{i}. {r['stock_code']} | "
            f"收盘价: {r['latest_close']:.2f} | "
            f"箱体: [{r['box_low']:.2f}, {r['box_high']:.2f}] | "
            f"突破幅度: {r['breakout_pct']*100:.2f}% | "
            f"MA10触及次数: {r['ma10_touch_count']} | "
            f"量比: {r['volume_ratio']:.2f}"
        )

    return results


if __name__ == "__main__":
    main()
