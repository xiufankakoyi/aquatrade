"""
MACD 绿柱凹函数收缩买入 + 红柱收缩卖出策略验证 (LanceDB 版本)

买入规则：
    1. 连续4天MACD柱为绿（柱值 < 0）
    2. 这4天柱值依次递增（即绿柱持续收缩）
    3. 收缩的幅度逐日加大（即相邻日差递增，形成凹函数形态）
    满足以上条件后，第5天开盘买入

卖出规则：
    出现红柱（柱值 > 0）且红柱开始缩短的第一天（即柱值 < 前一天）卖出
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import polars as pl
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

from config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradeResult:
    """交易结果"""
    stock_code: str
    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    return_pct: float
    hold_days: int
    green_bar_values: Tuple[float, float, float, float]
    contraction_speeds: Tuple[float, float, float]


def calculate_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    计算 MACD 指标
    
    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = pd.Series(close).ewm(span=fast, adjust=False).mean().values
    ema_slow = pd.Series(close).ewm(span=slow, adjust=False).mean().values
    macd_line = ema_fast - ema_slow
    signal_line = pd.Series(macd_line).ewm(span=signal, adjust=False).mean().values
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def check_green_bar_contraction(histogram: np.ndarray, idx: int, debug_stats: dict = None) -> Tuple[bool, Optional[Tuple[float, float, float, float]], Optional[Tuple[float, float, float]]]:
    """
    检查绿柱凹函数收缩条件
    
    条件：
    1. 连续4天MACD柱为绿（柱值 < 0）
    2. 这4天柱值依次递增（即绿柱持续收缩，负值变小）
    3. 收缩的幅度逐日加大（即相邻日差递增，形成凹函数形态）
    
    Args:
        histogram: MACD柱状图
        idx: 检查的结束索引（检查 idx-3, idx-2, idx-1, idx 这4天）
        debug_stats: 调试统计字典
    
    Returns:
        (是否满足条件, 4天柱值, 3天收缩速度)
    """
    if idx < 3:
        return False, None, None
    
    bars = histogram[idx-3:idx+1]
    
    if not np.all(bars < 0):
        return False, None, None
    
    if debug_stats is not None:
        debug_stats["green_4days"] += 1
    
    if not (bars[0] < bars[1] < bars[2] < bars[3]):
        return False, None, None
    
    if debug_stats is not None:
        debug_stats["increasing"] += 1
    
    speeds = np.diff(bars)
    
    if not (speeds[0] < speeds[1] < speeds[2]):
        return False, None, None
    
    if debug_stats is not None:
        debug_stats["concave"] += 1
    
    return True, tuple(bars), tuple(speeds)


def check_red_bar_shrink(histogram: np.ndarray, idx: int) -> bool:
    """
    检查红柱收缩卖出条件
    
    条件：
    1. 当前柱值为红（柱值 > 0）
    2. 当前柱值 < 前一天柱值（红柱开始缩短）
    
    Args:
        histogram: MACD柱状图
        idx: 检查的索引
    
    Returns:
        是否满足卖出条件
    """
    if idx < 1:
        return False
    
    curr_bar = histogram[idx]
    prev_bar = histogram[idx - 1]
    
    if curr_bar <= 0:
        return False
    
    if curr_bar >= prev_bar:
        return False
    
    return True


def run_backtest_with_lancedb(
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31",
    min_price: float = 1.0,
    max_price: float = 500.0,
    max_hold_days: int = 60,
) -> List[TradeResult]:
    """
    使用 LanceDB 运行回测
    
    Args:
        start_date: 回测开始日期
        end_date: 回测结束日期
        min_price: 最小价格过滤
        max_price: 最大价格过滤
        max_hold_days: 最大持仓天数
    
    Returns:
        交易结果列表
    """
    results = []
    
    print("正在初始化 LanceDB...")
    try:
        from data_svc.storage.lancedb_reader import LanceDBDataReader
        reader = LanceDBDataReader()
        print(f"LanceDB 初始化成功，路径: {reader.db_path}")
    except Exception as e:
        print(f"LanceDB 初始化失败: {e}")
        return results
    
    print(f"正在读取数据: {start_date} ~ {end_date}")
    
    fields = ['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
    
    try:
        df = reader.read(
            symbols=None,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )
        print(f"读取完成，数据行数: {len(df)}")
    except Exception as e:
        print(f"读取数据失败: {e}")
        return results
    
    if df.is_empty():
        print("数据为空")
        return results
    
    print(f"数据列: {df.columns}")
    
    stock_codes = df.select('stock_code').unique().to_series().to_list()
    print(f"股票数量: {len(stock_codes)}")
    
    trading_dates = sorted(df.select('trade_date').unique().to_series().to_list())
    print(f"交易日数量: {len(trading_dates)}")
    
    stats_debug = {"total": 0, "buy_signals": 0, "sell_signals": 0, "green_4days": 0, "increasing": 0, "concave": 0, "filtered_length": 0, "filtered_price": 0}
    
    for i, stock_code in enumerate(stock_codes):
        if (i + 1) % 500 == 0:
            print(f"处理进度: {i+1}/{len(stock_codes)}, 已找到 {len(results)} 笔交易, debug: {stats_debug}")
        
        try:
            stock_df = df.filter(pl.col('stock_code') == stock_code).sort('trade_date')
            
            if len(stock_df) < 50:
                stats_debug["filtered_length"] += 1
                continue
            
            close = stock_df['close'].to_numpy()
            dates = stock_df['trade_date'].to_numpy()
            
            if close[-1] < min_price or close[-1] > max_price:
                stats_debug["filtered_price"] += 1
                continue
            
            stats_debug["total"] += 1
            
            macd_line, signal_line, histogram = calculate_macd(close)
            
            in_position = False
            buy_idx = None
            buy_price = None
            green_bars = None
            contraction_speeds = None
            
            for j in range(35, len(histogram)):
                if not in_position:
                    is_buy, bars, speeds = check_green_bar_contraction(histogram, j, stats_debug)
                    
                    if is_buy:
                        stats_debug["buy_signals"] += 1
                        
                        buy_idx = j + 1
                        if buy_idx >= len(close):
                            continue
                        
                        in_position = True
                        buy_price = close[buy_idx]
                        green_bars = bars
                        contraction_speeds = speeds
                else:
                    hold_days = j - buy_idx
                    
                    if hold_days >= max_hold_days:
                        sell_idx = j
                        sell_price = close[sell_idx]
                        return_pct = (sell_price - buy_price) / buy_price * 100
                        
                        results.append(TradeResult(
                            stock_code=stock_code,
                            buy_date=str(dates[buy_idx]),
                            buy_price=buy_price,
                            sell_date=str(dates[sell_idx]),
                            sell_price=sell_price,
                            return_pct=return_pct,
                            hold_days=hold_days,
                            green_bar_values=green_bars,
                            contraction_speeds=contraction_speeds,
                        ))
                        
                        in_position = False
                        buy_idx = None
                        buy_price = None
                        continue
                    
                    if check_red_bar_shrink(histogram, j):
                        stats_debug["sell_signals"] += 1
                        
                        sell_idx = j
                        sell_price = close[sell_idx]
                        return_pct = (sell_price - buy_price) / buy_price * 100
                        
                        results.append(TradeResult(
                            stock_code=stock_code,
                            buy_date=str(dates[buy_idx]),
                            buy_price=buy_price,
                            sell_date=str(dates[sell_idx]),
                            sell_price=sell_price,
                            return_pct=return_pct,
                            hold_days=hold_days,
                            green_bar_values=green_bars,
                            contraction_speeds=contraction_speeds,
                        ))
                        
                        in_position = False
                        buy_idx = None
                        buy_price = None
                
        except Exception as e:
            continue
    
    return results


def analyze_results(results: List[TradeResult]) -> Dict:
    """
    分析回测结果
    
    Returns:
        统计结果字典
    """
    if not results:
        return {"error": "没有找到符合条件的交易"}
    
    returns = np.array([r.return_pct for r in results])
    hold_days = np.array([r.hold_days for r in results])
    
    win_count = np.sum(returns > 0)
    lose_count = np.sum(returns < 0)
    flat_count = np.sum(returns == 0)
    total_count = len(returns)
    
    win_rate = win_count / total_count * 100
    
    avg_return = np.mean(returns)
    median_return = np.median(returns)
    
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]
    
    avg_win = np.mean(positive_returns) if len(positive_returns) > 0 else 0
    avg_lose = np.mean(negative_returns) if len(negative_returns) > 0 else 0
    
    profit_factor = abs(np.sum(positive_returns) / np.sum(negative_returns)) if np.sum(negative_returns) != 0 else float('inf')
    
    percentiles = {
        "10%": np.percentile(returns, 10),
        "25%": np.percentile(returns, 25),
        "50%": np.percentile(returns, 50),
        "75%": np.percentile(returns, 75),
        "90%": np.percentile(returns, 90),
    }
    
    avg_hold_days = np.mean(hold_days)
    median_hold_days = np.median(hold_days)
    
    contraction_speeds = np.array([sum(r.contraction_speeds) for r in results])
    high_speed_mask = contraction_speeds > np.median(contraction_speeds)
    high_speed_returns = returns[high_speed_mask]
    low_speed_returns = returns[~high_speed_mask]
    
    high_speed_win_rate = np.sum(high_speed_returns > 0) / len(high_speed_returns) * 100 if len(high_speed_returns) > 0 else 0
    low_speed_win_rate = np.sum(low_speed_returns > 0) / len(low_speed_returns) * 100 if len(low_speed_returns) > 0 else 0
    
    return {
        "total_trades": total_count,
        "win_count": int(win_count),
        "lose_count": int(lose_count),
        "flat_count": int(flat_count),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "median_return": median_return,
        "avg_win": avg_win,
        "avg_lose": avg_lose,
        "profit_factor": profit_factor,
        "percentiles": percentiles,
        "max_return": np.max(returns),
        "max_loss": np.min(returns),
        "std_return": np.std(returns),
        "avg_hold_days": avg_hold_days,
        "median_hold_days": median_hold_days,
        "high_speed_win_rate": high_speed_win_rate,
        "low_speed_win_rate": low_speed_win_rate,
        "high_speed_avg_return": np.mean(high_speed_returns) if len(high_speed_returns) > 0 else 0,
        "low_speed_avg_return": np.mean(low_speed_returns) if len(low_speed_returns) > 0 else 0,
    }


def main():
    """主函数"""
    print("=" * 60)
    print("MACD 绿柱凹函数收缩买入 + 红柱收缩卖出策略验证")
    print("(LanceDB 数据源)")
    print("=" * 60)
    print()
    print("买入规则：")
    print("  1. 连续4天MACD柱为绿（柱值 < 0）")
    print("  2. 这4天柱值依次递增（绿柱持续收缩）")
    print("  3. 收缩幅度逐日加大（凹函数形态）")
    print("  满足条件后，第5天开盘买入")
    print()
    print("卖出规则：")
    print("  出现红柱（柱值 > 0）且红柱开始缩短的第一天卖出")
    print()
    
    print("正在运行回测...")
    results = run_backtest_with_lancedb(
        start_date="2020-01-01",
        end_date="2024-12-31",
    )
    
    print()
    print("=" * 60)
    print("回测结果分析")
    print("=" * 60)
    
    stats = analyze_results(results)
    
    if "error" in stats:
        print(f"错误: {stats['error']}")
        return
    
    print(f"""
【基础统计】
  总交易次数: {stats['total_trades']}
  盈利次数: {stats['win_count']}
  亏损次数: {stats['lose_count']}
  持平次数: {stats['flat_count']}

【胜率与收益】
  胜率: {stats['win_rate']:.2f}%
  平均收益: {stats['avg_return']:.2f}%
  中位数收益: {stats['median_return']:.2f}%
  收益标准差: {stats['std_return']:.2f}%

【持仓时间】
  平均持仓天数: {stats['avg_hold_days']:.1f} 天
  中位数持仓天数: {stats['median_hold_days']:.1f} 天

【盈亏分析】
  平均盈利: {stats['avg_win']:.2f}%
  平均亏损: {stats['avg_lose']:.2f}%
  盈亏比: {abs(stats['avg_win']/stats['avg_lose']):.2f}
  盈利因子: {stats['profit_factor']:.2f}

【收益分布】
  最大盈利: {stats['max_return']:.2f}%
  最大亏损: {stats['max_loss']:.2f}%
  10% 分位数: {stats['percentiles']['10%']:.2f}%
  25% 分位数: {stats['percentiles']['25%']:.2f}%
  50% 分位数: {stats['percentiles']['50%']:.2f}%
  75% 分位数: {stats['percentiles']['75%']:.2f}%
  90% 分位数: {stats['percentiles']['90%']:.2f}%

【收缩速度分析】
  高收缩速度组胜率: {stats['high_speed_win_rate']:.2f}%
  低收缩速度组胜率: {stats['low_speed_win_rate']:.2f}%
  高收缩速度组平均收益: {stats['high_speed_avg_return']:.2f}%
  低收缩速度组平均收益: {stats['low_speed_avg_return']:.2f}%
""")
    
    print("=" * 60)
    print("结论")
    print("=" * 60)
    
    if stats['win_rate'] > 50:
        print(f"✅ 该策略在历史数据上胜率为 {stats['win_rate']:.2f}%，高于 50%")
        print(f"   平均收益为 {stats['avg_return']:.2f}%，具有一定的正期望值")
    else:
        print(f"❌ 该策略在历史数据上胜率为 {stats['win_rate']:.2f}%，低于 50%")
        print(f"   平均收益为 {stats['avg_return']:.2f}%，可能需要优化")
    
    if stats['profit_factor'] > 1:
        print(f"✅ 盈利因子为 {stats['profit_factor']:.2f}，大于 1，策略具有正期望")
    else:
        print(f"❌ 盈利因子为 {stats['profit_factor']:.2f}，小于 1，策略可能亏损")
    
    if stats['high_speed_win_rate'] > stats['low_speed_win_rate']:
        print(f"✅ 收缩速度对胜率有正向影响:")
        print(f"   高收缩速度组胜率 {stats['high_speed_win_rate']:.2f}% > 低收缩速度组 {stats['low_speed_win_rate']:.2f}%")
    
    print()


if __name__ == "__main__":
    main()
